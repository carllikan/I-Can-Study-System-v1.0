from flask import Flask, request, jsonify
from vertexai.preview.language_models import TextGenerationModel
from gcp import *
from openai import OpenAI
import pinecone

app = Flask(__name__)

# Fetch configuration from GCP.py
run_conf = gcp_get_config()
project_id = gcp_project_id()
project_number = gcp_project_number(project_id)
# Set OpenAI and Pinecone API keys
openai_api_key = gcp_get_secret(project_number,run_conf.get( 'openai_api_key', 'openai_api_key_name' ))
pinecone_api = gcp_get_secret(project_number,run_conf.get( 'pinecone_api_key', 'pinecone_api_key_name' ))
# Initialize Pinecone
pinecone_env = run_conf.get( 'pinecone_env', 'us-west1-gcp' )
pinecone.init(api_key=pinecone_api, environment=pinecone_env)
client = OpenAI(api_key=openai_api_key)
pine_index = run_conf.get( 'pinecone_index', 'ics-addaxis')
index = pinecone.Index(pine_index)

@app.route('/', methods = ['GET', 'POST', 'DELETE'])
def process_text():
    """
    Processes a text-based query by making a GET request to the API.
    Fetches configuration from GCP.py, initializes Pinecone, and performs a search based on the input query.
    Builds and returns a JSON response containing the search results with highest similarity scores.
    
    return: A JSON response containing the search results along with relevant headers.
    """
    # Check if the request method is GET

    if request.method != 'GET':
        create_response("Please use GET to request the API", 400)

    # Extract parameters from the request
    # Validate the parameters
    request_args = request.args
    if "query" in request_args:
        query = request_args['query']
    else:
        return create_response("Please add query in request", 400)
    
    if len(query) <= 0:
        return create_response("Query are not allowed to be empty", 400)

    if 'type' in request_args:
        filt = request_args['type']
    else:
        filt = "all"
    if 'number' in request_args:
        number = request_args['number']
        number = int(number)
    else:
        number = 10

    # if 'page' in request_args:
    #     page = request_args['page']
    #     page = int(page)
    # else:
    #     page = 1
    allSummary = 'allSummary' in request_args and request_args['allSummary'] == 'True'
    singleSummary = 'singleSummary' in request_args and request_args['singleSummary'] == 'True'
    if 'threshold' in request_args:
        thres = float(request_args['threshold'])
    else:
        thres = 0.75
    if 'user_id' not in request_args:
        return create_response("Please provide user id", 400)
    if "user_stage" in request_args:
        user_stage = request_args["user_stage"]
        valid_stages = {'st-rapid-start':0, 'st-fundamentals':1, 'st-fundamentals-2':2, 'st-30-day-plan': 3, 'st-briefing':4, 'st-technique-training':5, 'st-ascent-i': 6, 'st-ascent-ii': 7, 'st-ascent-iii':8, 'st-base-camp': 9, 'st-camp-i': 10, 'st-camp-ii': 11, 'st-summit':12} 
        if user_stage.lower() not in valid_stages:
            return create_response("User Stage is not Valid, Please try again", 400)
        user_stage_nvalue = valid_stages[user_stage.lower()]

    else:
        return create_response("Please provide user stage", 400)
    
    # Call create_response_content to get the response content based on the search query
    ans, summary = create_response_content(filt.lower(), index, query=query, number=number, user_stage_nvalue=user_stage_nvalue, thres=thres, singleSummary=singleSummary, allSummary=allSummary)

    if allSummary:
        response = jsonify({'code': 200, 'response': ans, 'summary': summary})
    else:
        response = jsonify({'code': 200, 'response': ans})

    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,DELETE")
    return response

def create_item(type, singleSummary, **kwargs):
    """
    Creates and returns a dictionary item based on the given type.
    
    type: str, type of the item, either 'video' or 'document'.
    singleSummary: bool, indicates whether to include short description.
    kwargs: dict, additional keyword arguments containing the item's data.
    return: dict, item dictionary with keys like content_id, title, type, stage, description etc.
    """
    if type == 'video':
        # If singleSummary is True, include both short and full description in the item.
        if singleSummary:
            return {
                "content_id": kwargs.get('videoId', ''),
                "video_id": "JWplayer", 
                "title": kwargs.get('videoName', ''), 
                "type": "video", 
                "video_start_position": kwargs.get('timeStamp', ''), 
                "description_short": kwargs.get('text', ''), 
                "description": kwargs.get('speechTranscription', '')}
        # If singleSummary is False, include only full description in the item.
        return {
                "content_id": kwargs.get('videoId', ''),
                "video_id": "JWplayer", 
                "title": kwargs.get('videoName', ''), 
                "type": "video", 
                "video_start_position": kwargs.get('timeStamp', ''), 
                "description": kwargs.get('speechTranscription', '')}
    
    else:
        if singleSummary:
            return {"content_id": kwargs.get('contentId', ''), 
                    "title": kwargs.get('docName', ''), 
                    "type": "document", 
                    "description_short": kwargs.get('text', ''), 
                    "description": kwargs.get('originalText', '')}
        
        return {"content_id": kwargs.get('contentId', ''), 
                "title": kwargs.get('docName', ''), 
                "type": "document", 
                "description": kwargs.get('originalText', '')}


def create_embedding(article):
    """
    Creates an embedding vector for a given article using the OpenAI text-embedding-ada-002 model.
    
    article: str, input text article.
    return: list, the embedding vector for the input article.
    """
    return client.embeddings.create(input = [article], model="text-embedding-ada-002").data[0].embedding


def create_response(message, code):
    """
    Creates a JSON response with given message and code, and adds CORS headers.
    
    :param message: str, the response message.
    :param code: int, the HTTP status code.
    :return: Response object with the given message, code, and headers.
    """
    response = jsonify({'code': code, 'response': message})
    # Add CORS headers to the response
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,DELETE")
    return response


def create_response_content(type, index, **kwargs):
    """
    This function generates response content by querying an index based on the type 
    and additional parameters provided. It can handle three types: document, video, and all. 
    Depending on the type, it retrieves relevant content, optionally summarizes it using the PALM 
    Text Generation Model, and returns the results.
    
    type: str, Specifies the type of content to be retrieved, can be 'document', 'video', or 'all'.
    index: Object, Represents the pinecone index to be queried for retrieving content.
    kwargs: dict, Additional keyword arguments for filtering, summarization, etc.
    
    :return: Tuple, A tuple containing the list of retrieved items and optionally a summary of all items.
    """
    # Initialize the Text Generation Model
    text_model = TextGenerationModel.from_pretrained("text-bison@001")
    # to store the final results
    ans = {"metadata":{"query": kwargs.get("query", "query sent"), "type": type, "number": kwargs.get("number", 10)}, "results":[]}
    # Define the prompt for the Text Generation Model
    prompt = """role: "system" \n 
    "content":  "You are a truthful assistant!" \n 
    "role": "user" \n 
    content": Summarize below and dont use the word 'To summarize' at the beginning ---: {}"""
    if type == "document":
        # Create query vector and perform the search
        query_vector = create_embedding(kwargs.get("query", ""))
        search_response = index.query(
                top_k=kwargs.get("number", 10),
                vector=query_vector,
                filter={
                    "type": {"$eq": type},
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                },
                include_metadata=True)
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            if item['score']< kwargs.get("thres", ""):
                continue

            originalText = item["metadata"]["originalText"]
            docName = item["metadata"]["docName"]
            stage = item["metadata"]["stage"]
            contentId = item["metadata"]["contentId"]
            if kwargs.get("singleSummary", False):
                response = text_model.predict(prompt=prompt.format(originalText), temperature=0.2)
                text = response.text
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                           docName=docName, stage=stage, text=text, originalText=originalText))
            else:
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                           docName=docName, stage=stage, originalText=originalText))
    
    elif type == "video":
        # Create query vector and perform the search
        query_vector = create_embedding(kwargs.get("query", ""))
        search_response = index.query(
                top_k=kwargs.get("number", 10),
                vector=query_vector,
                filter={
                    "type": {"$eq": type},
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                },
                include_metadata=True)
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            if item['score']< kwargs.get("thres", 0.75):
                continue
            videoId = item['metadata']['videoId']
            videoName = item['metadata']['videoName']
            timeStamp = item['metadata']['startTimeSeconds']
            stage = item['metadata']['stage']
            speechTranscription = item['metadata']['speechTranscription']
            if kwargs.get("singleSummary", False):
                response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                text = response.text
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription))
            else:
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription))
    
    elif type == "all":
        # Create query vector and perform the search
        query_vector = create_embedding(kwargs.get("query", ""))
        search_response = index.query(
                top_k=kwargs.get("number", 0),
                vector=query_vector,
                filter = {
                    "type": {"$in":["document","video"]},
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                    },
                include_metadata=True )
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            if item['score']< kwargs.get("thres", 0):
                continue
            if item['metadata']['type'] == 'video':
                videoId = item['metadata']['videoId']
                videoName = item['metadata']['videoName']
                timeStamp = item['metadata']['startTimeSeconds']
                stage = item['metadata']['stage']
                speechTranscription = item['metadata']['speechTranscription']
                if kwargs.get("singleSummary", False):
                    response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                    text = response.text
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription))

                else:
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription))

            elif item['metadata']['type'] == 'document':
                originalText = item["metadata"]["originalText"]
                docName = item["metadata"]["docName"]
                stage = item["metadata"]["stage"]
                contentId = item["metadata"]["contentId"]
                if kwargs.get("singleSummary", False):
                    response = text_model.predict(prompt=prompt.format(originalText), temperature=0.2)
                    text = response.text
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                           docName=docName, stage=stage, text=text, originalText=originalText))
                else:
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                           docName=docName, stage=stage, originalText=originalText))
                

    else:

        return "type must be all, video or document" 

    if kwargs.get("allSummary", False):
        all_text = ""
        for a in ans["results"]:
            if a["type"] == "document":
                all_text += f"""\n  ("text": {a["description"]}, "docName": {a["title"]}) """
            else:
                all_text += f"""\n  ("text": {a["description"]}, "videoName": {a["title"]}) """
        response = text_model.predict(prompt=prompt.format(all_text), temperature=0.2)
        summary = response.text
        return ans, summary
    return ans, "empty"

       