from langchain.tools import tool
from zoho.crm_client import ZohoCRMClient
import os
from dotenv import load_dotenv
load_dotenv()
from utils.query_validator import validate_and_format_coql

refresh_token = os.getenv("ZDH_1_REFRESH")
client_id = os.getenv("ZDH_1_CLIENTID")
client_secret = os.getenv("ZDH_1_CLIENTSECRET")
zapikey = os.getenv("MAIL_API_KEY")

zoho = ZohoCRMClient(refresh_token, client_id, client_secret,zapikey)



@tool("get_fields_tool")
def get_fields_tool(module: str, datatypes: list):
    """
    <use_case>
    Retrieves the exact API field names from a Zoho CRM module, filtered by specified data types.
    </use_case>

    <important_notes>
    - This tool supports filtering by one or more Zoho CRM field data types.
    - Use specific data types whenever possible to minimize response size and token usage.
    - Avoid using "ALL" except in rare cases (see guidance below).
    </important_notes>

    <arguments>
        module (str): The Zoho CRM module name (e.g., "Leads", "Contacts").
        datatypes (list[str]): A list of data types to filter fields. Valid options include:
            "picklist", "text", "ownerlookup", "email", "datetime", "boolean", "bigint",
            "profileimage", "fileupload", "website", "rollup_summary", "percent",
            "imageupload", "date", "integer", "multiselectpicklist", "autonumber",
            "currency", "double", "userlookup", "phone", "textarea", "formula", or "ALL".
    </arguments>
    """
    return zoho.get_fields(module, datatypes)




@tool("query_records_tool")
def query_records_tool(query: str):
    """
    <use_case>
    Executes a COQL (Zoho CRM Object Query Language) query to fetch records from a Zoho CRM module.
    Always use exact API field names obtained from `get_fields_tool`.
    </use_case>

    <important_notes>
    - SELECT * is strictly prohibited. Always specify explicit field names.
    - Field names must be the internal API names (e.g., 'Event_Status'), not UI labels.
    - String literals must use single quotes (e.g., 'Completed'), not double quotes.
    - The module name in the FROM clause must be plural and valid (e.g., 'Events', not 'Event').
    - When combining multiple conditions in WHERE, wrap logical groups in parentheses for clarity and correctness.
      Example: SELECT Event_Title FROM Events WHERE ((Event_Status = 'Completed') and (Event_Date > '2024-01-01'))
    - The query will be automatically validated and formatted before execution.
    </important_notes>

    <arguments>
        query (str): A COQL query string following Zoho CRM syntax rules.
    </arguments>
    """
    validation = validate_and_format_coql(query)

    print("-"*30)
    print("Validation",validation)
    print("-"*30)
    
    if not validation["valid"]:
        return {
            "success": False,
            "error": "INVALID_QUERY",
            "message": "Query validation failed",
            "details": {
                "original_query": query,
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
        }
    else:

        print("-"*30)
        print("query",query)
        print("-"*30)

        response = zoho.query_records(query)
        
        return {
            "response":response,
            "COQL_Validation":validation
        }



@tool("create_records_tool")
def create_records_tool(module: str, payload: dict):
    """
    <use_case>
    Creates one or more records in a specified Zoho CRM module.
    </use_case>

    <important_notes>
    - ⚠️ NEVER call this tool if any mandatory field is missing. Instead, ask the user for the missing information.
    - Use only official Zoho CRM **API field names** (e.g., "Deal_Name", not "Deal Name").
    - Lookup fields (e.g., Account, Owner, Pipeline) must be passed as: {"id": "record_id"}.
    - The payload must include a "data" key containing a list of 1–100 record objects.
    - The module name must be a valid Zoho CRM module (e.g., "Leads", "Deals", "Events").
    - To suppress automation triggers (e.g., workflows, approvals), include "trigger": [] in the payload.
    - For Discount field if the user ask to apply "10%" send the payload with "10%" as string.
    - For creating Quotes, Sales_Orders, Invoices and Purchase_Orders use Product_Name as product lookup. If the user give Product_Name or Product_Code use coql to get the product id then use in the subform.
    - Here is the subform api name for some modules: Quotes = Quoted_Items, Sales_Orders = Ordered_Items, Invoices = Invoiced_Items, Purchase_Orders=Purchase_Items.
    </important_notes>

    <arguments>
        module (str): The target Zoho CRM module (e.g., "Leads", "Deals", "Accounts").
        payload (dict): A dictionary containing:
            - "data" (list): List of record objects (1–100 records).
            - Optional "trigger" (list): Controls which automations run (e.g., ["workflow"]). Use [] to disable all.
    </arguments>

    <mandatory_fields_by_module>
        use "get_fields_tool" to know about the mandatory fields of the module.
    </mandatory_fields_by_module>

    <critical_reminder>
    If the user has not provided all mandatory fields for the target module,
    DO NOT invoke this tool. Prompt the user explicitly for the missing field(s).
    Example: "To create a Deal, I need the Deal Name, Stage, Pipeline, and Closing Date. Could you please provide them?"
    **Very Important Step:Display the data and ask for Approval before creating the record.**
    </critical_reminder>
    """
    return zoho.create_record(module, payload)




@tool("convert_lead_tool")
def convert_lead_tool(record_id: str, payload: dict):
    """
    <use_case>
    Converts a Zoho CRM Lead into a Contact and/or Account, and optionally creates a new Deal.
    This operation is irreversible—ensure all required data is validated before calling.
    </use_case>

    <important_notes>
    - The `record_id` must be a valid Zoho Lead record ID.
    - The payload must follow Zoho’s lead conversion API structure: {"data": [{...}]}.
    - If creating a Deal, the following fields are mandatory: Deal_Name, Closing_Date, Pipeline, Stage.
    </important_notes>

    <arguments>
        record_id (str): The unique ID of the Lead to be converted.
        payload (dict): A dictionary with a "data" key containing a list with one conversion object.  
    </arguments>

    <example_payload>
    {
      "data": [
        {
          "overwrite": true, -optional
          "notify_lead_owner": true, -optional
          "move_attachments_to": {"module": "Contacts"}, -optional
          "Accounts": {"id": "1234567890"}, -optional
          "Contacts": {}, -optional
          "Deals": {
            "Deal_Name": "Website Redesign",
            "Closing_Date": "2025-12-31",
            "Pipeline": "Standard Pipeline",
            "Stage": "Qualification"
          }, -optional
          "assign_to": {"id": "9876543210"}, -optional
          "carry_over_tags": {"Contacts": true, "Accounts": true, "Deals": false} -optional
        }
      ]
    }
    </example_payload>
    """
    return zoho.convert_lead(record_id, payload)




@tool("update_records_tool")
def update_records_tool(module_api_name: str, body: dict):
    """
    <use_case>
    Updates one or multiple existing records in a Zoho CRM module.
    This tool supports bulk updates (up to 100 records per call) and fine-grained control over field behavior,
    including subforms, picklist appending, lookup unlinking, and automation triggers.
    </use_case>

    <important_notes>
    - The `module_api_name` must be a valid Zoho CRM module API name (e.g., "Leads", "Deals", "Contacts").
    - Every record in `body["data"]` **must include an "id" field** with the record’s unique ID.
    - Field values must conform to data type, format, and length constraints—invalid data will cause the entire request to fail with "INVALID_DATA".
    - For updating Discount field if the user ask to apply "10%" send the payload with "10%" as string.
    - For updating line items use line items 'id' in the subform payload.
    </important_notes>

    <arguments>
        module_api_name (str): The API name of the target Zoho CRM module (e.g., "Leads", "Invoices").
        body (dict): A dictionary containing:
            - "data" (list): List of record objects to update (1–100 records). Each must contain "id".
            - Optional top-level keys:
            - Subform fields may be included using Zoho’s subform API structure.
    </arguments>
 
    <supported_modules>
        Leads, Accounts, Contacts, Deals, Campaigns, Tasks, Cases, Events, Calls, Solutions,
        Products, Vendors, PriceBooks, Quotes, SalesOrders, PurchaseOrders, Invoices, Appointments,
        Appointments_Rescheduled_History, Services, Notes, and Custom Modules.
    </supported_modules>

    <usage_guidance>
    - To update a single record: include its id in the "data" list (no separate `record_id` parameter needed).
    </usage_guidance>
    """
    return zoho.update_records(module_api_name, body)



@tool("send_mail_tool")
def send_mail_tool(to_mail: str, mail_subject: str, mail_content: str):
    """
    <use_case>
    Sends an HTML-formatted email to a specified recipient using a Zoho CRM function.
    </use_case>

    <important_notes>
    - The email body (`mail_content`) must be valid HTML.
    - Use `<br>` for line breaks. Avoid plain newline characters (`\n`), as they may not render correctly.
    - Do not include `<html>`, `<head>`, or `<body>` tags—only the inner content (e.g., paragraphs, lists, links).
    - Ensure the recipient email address (`to_mail`) is valid and properly formatted.
    - This tool does not support attachments or CC/BCC fields in its current form.
    </important_notes>

    <arguments>
        to_mail (str): The recipient’s email address (e.g., "user@example.com").
        mail_subject (str): The subject line of the email.
        mail_content (str): The HTML body of the email. Example:
            "Hello,<br><br>Thank you for your interest in our service.<br><br>Best regards,<br>Team"
    </arguments>
    """
    return zoho.send_mail(to_mail, mail_subject, mail_content)


@tool("get_module_api_name_tool")
def get_module_api_name_tool():
    """
    <use_case>
    Retrieves a mapping of user-friendly Zoho CRM module names (e.g., "Leads", "Deals") 
    </use_case>

    <important_notes>
    - This is especially useful for custom modules where the API name may not match the display name.
    - Always use the returned API name in subsequent tool calls (e.g., in `query_records_tool`, `update_records_tool`).
    </important_notes>
    """
    return zoho.get_module_api_name()


@tool("get_specific_record_tool")
def get_specific_record_tool(module: str, record_id: str):
    """
    <use_case>
    Fetches the complete details of a single Zoho CRM record, including all fields and subform data.
    Use this when you need full context about a record.
    </use_case>

    <arguments>
        module (str): The API name of the Zoho CRM module (e.g., "Leads", "Quotes").
        record_id (str): The unique ID of the record to retrieve.
    </arguments>
    """
    return zoho.get_specific_record(module, record_id)





@tool("create_task_tool")
def create_task_tool(payload):
    """
    <use_case>
    Creates a Task record in Zoho CRM.
    </use_case>

    <important_notes>
    - `Subject` is **mandatory**.
    - `Who_Id` should reference a **Lead or Contact** record ID.
    - `What_Id` can reference **any module** record ID.
    - If `What_Id` is provided, `$se_module` is **mandatory** and must be the
      API name of the related module (e.g., "Deals").
    - Use `get_module_api_name_tool` if the module API name is unknown.
    </important_notes>

    <arguments>
        payload (dict): Task creation payload in the format:
            {
                "data": [
                    {
                        "Subject": str,                 # required
                        "Due_Date": str,               # YYYY-MM-DD (optional)
                        "Status": str,                 # optional
                        "Who_Id": { "id": str },       # Lead/Contact ID (preferred)
                        "What_Id": { "id": str },      # Any module record ID (optional)
                        "$se_module": str              # required if What_Id is used
                    }
                ]
            }
    </arguments>
    """
    return zoho.create_Task(payload)
