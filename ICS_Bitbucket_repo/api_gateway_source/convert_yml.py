import os
from dotenv import load_dotenv
load_dotenv()
ics_global_search_cloud_run_url = os.environ['ICS_GLOBAL_SEARCH_CLOUD_RUN_URL'].replace('"', "").strip()
ics_mind_map_evaluation_cloud_run_url = os.environ['ICS_MIND_MAP_EVALUATION_CLOUD_RUN_URL'].replace('"', "").strip()
ics_reflection_evaluation_cloud_run_url = os.environ['ICS_REFLECTION_EVALUATION_CLOUD_RUN_URL'].replace('"', "").strip()
ics_evaluation_api_cloud_run_url = os.environ['ICS_EVALUATION_API_CLOUD_RUN_URL'].replace('"', "").strip()

# use API Cloud Run URL for independent testing
mm_api_cloud_run_url = ics_mind_map_evaluation_cloud_run_url.replace("ics-mind-map-evaluation-pipeline", "ics-mind-map-evaluation-api")
ref_api_cloud_run_url = ics_reflection_evaluation_cloud_run_url.replace("ics-reflection-evaluation-pipeline", "ics-reflection-evaluation-api")
###############
'''
When create api gateways for global search, mind map evaluation and reflection evaluation
please commendted out the followings
'''

###############
########################### Replace URL Address of GLOBAL Search on Cloud Run ###########################  
# with open('./ics_global_search_api_gateway/openapi.yml', 'r') as file:
#     content = file.read()

# content = content.replace('${CLOUD_RUN_URL}', ics_global_search_cloud_run_url)
# print(content)
# with open('./ics_global_search_api_gateway/openapi.yml', 'w') as file:
#     file.write(content)

# ########################### Replace URL Address of Mind Map Evaluation on Cloud Run ###########################  
# with open('./ics_mind_map_evaluation_api_gateway/openapi.yml', 'r') as file:
#     content = file.read()

# content = content.replace('${CLOUD_RUN_URL}', ics_mind_map_evaluation_cloud_run_url)
# print(content)
# with open('./ics_mind_map_evaluation_api_gateway/openapi.yml', 'w') as file:
#     file.write(content)

########################### Replace URL Address of Reflection Evaluation on Cloud Run ###########################  

# with open('./ics_reflection_evaluation_api_gateway/openapi.yml', 'r') as file:
#     content = file.read()
# content = content.replace('${CLOUD_RUN_URL}', ics_reflection_evaluation_cloud_run_url)
# print(content)
# with open('./ics_reflection_evaluation_api_gateway/openapi.yml', 'w') as file:
#     file.write(content)
    
########################### Replace URL Address of  Evaluation  api on Cloud Run ###########################  
with open('./openapi.yml', 'r') as file:
    content = file.read()
if 'EVALUATION_API_CLOUD_RUN_URL' in content:
    content = content.replace('EVALUATION_API_CLOUD_RUN_URL', ics_evaluation_api_cloud_run_url)
    print(content)
if 'GLOBAL_SEARCH_CLOUD_RUN_URL' in content:
    content = content.replace('GLOBAL_SEARCH_CLOUD_RUN_URL', ics_global_search_cloud_run_url)
if 'MIND_MAP_CLOUD_RUN_URL' in content:
    content = content.replace('MIND_MAP_CLOUD_RUN_URL', mm_api_cloud_run_url)
if 'REFLECTION_CLOUD_RUN_URL' in content:
    content = content.replace('REFLECTION_CLOUD_RUN_URL', ref_api_cloud_run_url)

with open('./ics_evaluation_api_gateway/openapi.yml', 'w') as file:
    file.write(content)
