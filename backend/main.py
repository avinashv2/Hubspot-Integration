from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from integrations.hubspot import authorize_hubspot, get_hubspot_credentials, get_items_hubspot, oauth2callback_hubspot

app = FastAPI()

origins = [
    "http://localhost:3000",  # Frontend Address
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
def read_root():
    return {'Ping': 'Pong'}

class CredentialsRequest(BaseModel):
    user_id: str
    org_id: str

class HubSpotCredentials(BaseModel):
    credentials: dict

# HubSpot
@app.post('/integrations/hubspot/authorize')
async def authorize_hubspot_integration(data: CredentialsRequest):
    return await authorize_hubspot(data.user_id, data.org_id)

@app.get('/integrations/hubspot/oauth2callback')
async def oauth2callback_hubspot_integration(request: Request):
    return await oauth2callback_hubspot(request)

@app.post('/integrations/hubspot/credentials')
async def get_hubspot_credentials_integration(data: CredentialsRequest):
    return await get_hubspot_credentials(data.user_id, data.org_id)

@app.post('/integrations/hubspot/load')
async def get_hubspot_items(data: HubSpotCredentials):
    return await get_items_hubspot(data.credentials)
