import requests
from langsmith import Client
from dotenv import load_dotenv
load_dotenv()
import os

client = Client() 


def tool_error(
    *,
    tool: str,
    error_type: str,
    message: str,
    status_code: int | None = None,
    details: dict | None = None,
):
    return {
        "success": False,
        "tool": tool,
        "error": {
            "type": error_type,       
            "message": message,        
            "status_code": status_code,
            "details": details or {}
        }
    }


class ZohoCRMClient:
    def __init__(self, refresh_token, client_id, client_secret, zapikey):
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self.refresh_access_token()
        self.zapikey = zapikey

    def refresh_access_token(self):
        url = (
            f"https://accounts.zoho.com/oauth/v2/token?refresh_token={self.refresh_token}"
            f"&client_id={self.client_id}"
            f"&client_secret={self.client_secret}"
            f"&grant_type=refresh_token"
        )
        response = requests.post(url)
        if response.status_code == 200:
            access_token = response.json().get("access_token")
            print("New Access Token:", access_token)
            return access_token
        else:
            print("Failed to refresh token:", response.json())
            return None

    def get_records(self, module: str, fields: list = None):

        print("modules",module)
        print("fields",fields)

        if not self.access_token:
            self.access_token = self.refresh_access_token()

        url = f"https://www.zohoapis.com/crm/v8/{module}?fields="+",".join(fields)

        print(url)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url, headers=headers)
        print(response.json())
        if response.status_code == 401:  
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_records(module, fields)  

        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_records_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }



    def get_specific_record(self, module: str, record_id:str):

        print("modules",module)

        if not self.access_token:
            self.access_token = self.refresh_access_token()

        url = f"https://www.zohoapis.com/crm/v8/{module}/{record_id}"

        print(url)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url, headers=headers)
        print(response.json())
        if response.status_code == 401: 
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_specific_record(module, record_id) 

        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_records_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }


    def get_fields(self, module: str, datatypes: list):
        url = f"https://www.zohoapis.com/crm/v8/settings/fields?module={module}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_fields(module, datatypes)

        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_fields_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        data = response.json()


        fetch_all = ("ALL" in datatypes or "all" in datatypes) if datatypes else False


        fields = []
        for field in data.get("fields", []):
            data_type = field.get("data_type", "")

            if not fetch_all and datatypes and data_type not in datatypes:
                continue

            pick_list_values = field.get("pick_list_values", [])

            fields.append({
                "api_name": field.get("api_name", ""),
                "data_type": data_type,
                "mandatory": field.get("system_mandatory", False),
                "values": [item.get("display_value") for item in pick_list_values]
            })

        return {
            "success": True,
            "data": fields
        }


 

    def query_records(self, query: str):
      url = "https://www.zohoapis.com/crm/v8/coql"

      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Zoho-oauthtoken {self.access_token}"
      }

      payload = {
          "select_query": query
      }

      response = requests.post(url, headers=headers, json=payload)
      print(response)
      if response.status_code == 401:
        print("⛔ Token expired — refreshing...")
        self.access_token = self.refresh_access_token()
        if self.access_token:
            return self.query_records(query) 
        else:
            raise Exception("Token refresh failed")

      if response.status_code == 204:
          return {"data":[]} 
    
      if response.status_code not in (200, 201):
        return tool_error(
                tool="query_records_tools",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

      return {
            "success": True,
            "data": response.json()
        }



    def create_record(self, module: str, payload: dict):
        url = f"https://www.zohoapis.com/crm/v8/{module}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        print("POST URL:", url)
        print("PAYLOAD:", payload)

        response = requests.post(url, headers=headers, json=payload)

        print("POST RESPONSE RAW:", response)
        print("POST RESPONSE JSON:", response.json() if response.text else None)

        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.create_record(module, payload)

        if response.status_code not in (200, 201):
            return tool_error(
                tool="create_records_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }
    

    def create_Task(self, payload: dict):
        url = f"https://www.zohoapis.com/crm/v8/Tasks"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        print("POST URL:", url)
        print("PAYLOAD:", payload)

        response = requests.post(url, headers=headers, json=payload)

        print("POST RESPONSE RAW:", response)
        print("POST RESPONSE JSON:", response.json() if response.text else None)

        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.create_Task(payload)

        if response.status_code not in (200, 201):
            return tool_error(
                tool="create_task_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }


    def get_all_users(self, user_type:str):
        url = f"https://www.zohoapis.com/crm/v8/users?type={user_type}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url,headers=headers)

        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_all_users(user_type)

        if response.status_code not in (200, 201):
            print(f"❌ API error {response.status_code}: {response.text}")
            response.raise_for_status()

        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_all_users_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }


    def get_specific_user(self, userID:str):
        url = f"https://www.zohoapis.com/crm/v8/users?{userID}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url,headers=headers)

        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_specific_user(userID)

        if response.status_code not in (200, 201):
            print(f"❌ API error {response.status_code}: {response.text}")
            response.raise_for_status()

        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_specific_user_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }



    def update_records(self, module: str, payload: dict, record_id: str = None):
        is_single = (
            "data" in payload and 
            len(payload["data"]) == 1 and 
            "id" in payload["data"][0]
        )

        # Build URL
        if is_single:
            record_id = payload["data"][0]["id"]
            url = f"https://www.zohoapis.com/crm/v8/{module}/{record_id}"
        else:
            url = f"https://www.zohoapis.com/crm/v8/{module}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        print("PUT URL:", url)
        print("PAYLOAD:", payload)

        response = requests.put(url, headers=headers, json=payload)

        print("PUT RESPONSE RAW:", response)
        print("PUT RESPONSE JSON:", response.json() if response.text else None)

        # Token refresh
        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.update_records(module, payload)


        if response.status_code not in (200, 201):
            return tool_error(
                tool="update_records_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }



    def convert_lead(self,record_id:str, payload:dict):
        
        url = f"https://www.zohoapis.com/crm/v8/Leads/{record_id}/actions/convert"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        print("PUT URL:", url)
        print("PAYLOAD:", payload)

        response = requests.post(url, headers=headers, json=payload)

        print("PUT RESPONSE RAW:", response)
        print("PUT RESPONSE JSON:", response.json() if response.text else None)

        # Handle token expiry
        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.convert_lead(record_id, payload)

        if response.status_code not in (200, 201):
            return tool_error(
                tool="convert_lead_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }

    def send_mail(self, to_mail: str, mail_subject: str, mail_content:str):
        url = f"https://www.zohoapis.com/crm/v7/functions/agentmail/actions/execute"

        params = {
            "auth_type": "apikey",       
            "zapikey": self.zapikey,
        }
        payload = {
            "toMail":to_mail,
            "mailSubject":mail_subject,
            "mailContent":mail_content
        }

        print("PUT URL:", url)
        print("PAYLOAD:", payload)

        response = requests.post(url, json=payload,params=params)

        print("PUT RESPONSE RAW:", response)
        print("PUT RESPONSE JSON:", response.json() if response.text else None)

        if response.status_code not in (200, 201):
            return tool_error(
                tool="send_mail_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        return {
            "success": True,
            "data": response.json()
        }

    
    def get_module_api_name(self):
        url = f"https://www.zohoapis.com/crm/v8/settings/modules"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }

        response = requests.get(url,headers=headers)
        print("Module response",response)

        # Handle token expiry
        if response.status_code == 401:
            print("⛔ Token expired — refreshing...")
            self.access_token = self.refresh_access_token()
            return self.get_module_api_name()

        # Other errors
        if response.status_code not in (200, 201):
            print(f"❌ API error {response.status_code}: {response.text}")
            response.raise_for_status()

        # return response.json()
        if response.status_code not in (200, 201):
            return tool_error(
                tool="get_module_api_name_tool",
                error_type="API_ERROR",
                message="Zoho CRM rejected the request",
                status_code=response.status_code,
                details=response.json() if response.text else {}
            )

        res_data = []
        data = response.json()
        
        for module in data.get('modules',[]):

          res_data.append({
              'label': module.get('actual_plural_label', ''),
              'api_name': module.get('api_name', '')
          })

        return {
            "success": True,
            "data": res_data
        }
