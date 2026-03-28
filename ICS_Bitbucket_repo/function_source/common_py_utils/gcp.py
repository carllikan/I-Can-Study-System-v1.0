# requirements.txt must have these additional resources
# google-api-python-client
# oauth2client
# firebase-admin
# google-cloud-secret-manager
# google-auth

def gcp_logger():
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(format='[%(levelname)s: %(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s',level=logging.DEBUG)
    return logger

def gcp_get_config():
    # https://cloud.google.com/firestore/docs/query-data/get-data#get_a_document
    from firebase_admin import firestore

    db = firestore.Client()
    doc_ref = db.collection('function_configuration').document('project_variables')
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    else:
        return {}

# This returns the Project ID
def gcp_project_id():
    import google.auth
    _, project_id = google.auth.default()
    return project_id

# This returns the Project Number.
def gcp_project_number( project_id ):
    from googleapiclient import discovery
    from oauth2client.client import GoogleCredentials

    credentials = GoogleCredentials.get_application_default()
    service = discovery.build( 'compute', 'v1', credentials=credentials )
    request = service.projects().get( project=project_id )
    response = request.execute()
    # eg: {...'defaultServiceAccount': '430401774617-compute@developer.gserviceaccount.com', ...}
    default_service_account = response.get( 'defaultServiceAccount', '0-x' )
    parts = default_service_account.split( '-' )
    return parts[0]

# Returns the value in the secret. Be careful. If the secret does not exists
# Then throws an exception with return a 500 error
def gcp_get_secret( project_number, secret_name ):
    # https://googleapis.dev/python/secretmanager/0.1.1/gapic/v1beta1/api.html
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_number}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version( name=name )
    return response.payload.data.decode( "UTF-8" )