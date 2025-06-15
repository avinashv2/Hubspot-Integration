# hubspot.py
import json
import base64
import secrets
import os

import httpx
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8000/integrations/hubspot/oauth2callback"
authorization_url = "https://app-na2.hubspot.com/oauth/authorize"
scopes = "crm.objects.contacts.read crm.objects.contacts.write"

async def authorize_hubspot(user_id, org_id):
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    url = (
        f"{authorization_url}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes.replace(' ', '%20')}"
        f"&response_type=code"
        f"&state={encoded_state}"
    )
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    return {"url": url}

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))

    params = dict(request.query_params)
    code = params.get("code")
    encoded_state = params.get("state")
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    token_url = "https://api.hubapi.com/oauth/v1/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        tokens = response.json()
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(tokens), expire=600)
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

def create_directory_node(id, name):
    return IntegrationItem(
        id=id,
        type="directory",
        name=name,
        children=[]
    )

def create_integration_item_metadata_object(contact):
    props = contact.get("properties", {})
    item = IntegrationItem(
        id=contact.get("id"),
        parent_id="hubspot_contacts",
        parent_path_or_name="Contacts",
        type="hubspot.contact",
        directory=False,
        name=f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
        creation_time=props.get("createdate"),
        last_modified_time=props.get("lastmodifieddate"),
        children=[],
        mime_type="contact"
    )
    return item

async def get_items_hubspot(credentials):
    url = 'https://api.hubapi.com/crm/v3/objects/contacts'
    headers = {
        "authorization": f"Bearer {credentials.get('access_token')}"
    }
    params = {
        "limit": 10,
        "properties": "firstname,lastname,createdate,lastmodifieddate",
        "archived": False
    }
    contacts = []
    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            response_data = response.json()

            # Add current page results
            contacts.extend(response_data.get("results", []))

            # Check for next page
            paging = response_data.get("paging")
            if paging and "next" in paging:
                params["after"] = paging["next"]["after"]
            else:
                break
    contacts_parent = create_directory_node("hubspot_contacts", "Contacts")
    for contact in contacts:
        contacts_parent.children.append(create_integration_item_metadata_object(contact))

    return [contacts_parent]
