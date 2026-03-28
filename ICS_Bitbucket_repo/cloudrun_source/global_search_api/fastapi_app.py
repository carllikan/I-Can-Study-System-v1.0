from flask import Flask, request, jsonify
from flask_utils import apply_security_headers
from fuzzywuzzy import fuzz, process
# from vertexai.preview.language_models import TextGenerationModel
from vertexai.preview.generative_models import GenerativeModel
from gcp import *
import json
from std_response import *
from openai import OpenAI
from pinecone import Pinecone
import logging
import os
from google.cloud import firestore
# JsonParser
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.prompts import ChatPromptTemplate
from langchain.prompts import HumanMessagePromptTemplate
from google.generativeai.types.safety_types import HarmBlockThreshold, HarmCategory
from langchain_core.output_parsers import JsonOutputParser
from vertexai.language_models import TextEmbeddingModel
import memory_prompt


GOOGLE_API_KEY = "AIzaSyB78W4BU3-vSG6kVZv_stpUmmn1Hb6Cl4I" 
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
app = Flask(__name__)

app.after_request(apply_security_headers)
logger = logging.getLogger()

# Fetch configuration from GCP.py
run_conf = gcp_get_config()
project_id = gcp_project_id()
project_number = gcp_project_number(project_id)
# Set OpenAI and Pinecone API keys
openai_api_key = gcp_get_secret(project_number,run_conf.get( 'openai_api_key', 'openai_api_key_name' ))
pinecone_api = gcp_get_secret(project_number,run_conf.get( 'pinecone_api_key', 'pinecone_api_key_name' ))
# Initialize Pinecone
pinecone_env = run_conf.get( 'pinecone_env', 'us-west1-gcp' )
pc = Pinecone(api_key=pinecone_api)
client = OpenAI(api_key=openai_api_key)
pine_index = run_conf.get( 'pinecone_index', 'ics-ai-vector-index')
# pine_index = "gecko-index"
index = pc.Index(pine_index)
ALL_CHUNKS = []
ALL_LC_CHUNKS = [] 

@app.before_request
def load_data():
    global ALL_CHUNKS
    global ALL_LC_CHUNKS
    # Assuming 'sample_data.json' is your file containing the list of dictionaries
    with open('all_chunks.json', 'r') as file:
        ALL_CHUNKS = json.load(file)['results']
        file.close()
    with open('all_lc_chunks.json', 'r') as file:
        ALL_LC_CHUNKS = json.load(file)['results']
        file.close()

@app.route('/', methods = ['GET'])
def process_text():
    """
    Processes a text-based query by making a GET request to the API.
    Fetches configuration from GCP.py, initializes Pinecone, and performs a search based on the input query.
    Builds and returns a JSON response containing the search results with highest similarity scores.
    
    return: A JSON response containing the search results along with relevant headers.
    """
    # Check if the request method is GET

    if request.method != 'GET':
        create_response("Please use GET to request the API", 405, request.method)
    # Extract parameters from the request
    # Validate the parameters
    request_args = request.args
    if "query" in request_args:
        query = request_args['query']
    else:
        return create_response("Please add query in request", 400, request.method)
    
    if len(query) <= 0:
        return create_response("Query are not allowed to be empty", 400, request.method)

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
        thres = 0.1
    if 'user_id' not in request_args:
        return create_response("Please provide user id", 400, request.method)
    if "user_stage" in request_args:
        user_stage = request_args["user_stage"]
        valid_stages = {'st-rapid-start':0, 'st-fundamentals':1, 'st-fundamentals-2':2, 'st-30-day-plan': 3, 'st-briefing':4, 'st-technique-training':5, 'st-ascent-i': 6, 'st-ascent-ii': 7, 'st-ascent-iii':8, 'st-base-camp': 9, 'st-camp-i': 10, 'st-camp-ii': 11, 'st-summit':12} 
        if user_stage.lower() not in valid_stages:
            return create_response("User Stage is not Valid, Please try again", 400, request.method)
        user_stage_nvalue = valid_stages[user_stage.lower()]

    else:
        return create_response("Please provide user stage", 400, request.method)
    logger.info(f"checking type {filt} before calling create_response_content")
    
    query_classifer_response = query_classier(query)
    query_type = query_classifer_response.get("label", None)
    query_source = query_classifer_response.get("source", None)
    

    # Call create_response_content to get the response content based on the search query
    ans, summary = create_response_content(filt.lower(), index, query=query, number=number, user_stage_nvalue=user_stage_nvalue, thres=thres, singleSummary=singleSummary, allSummary=allSummary, query_type=query_type, query_source=query_source)
    logger.info(f"checking {ans},{summary}")
    if isinstance(ans, str):
        return create_response(ans, 400, request.method)
    
    if allSummary:
        ans["summary"] = summary
        if ans["results"] == [] or summary == "There are no relevant materials at the moment. Please try a new query.":
            db_firestore = firestore.Client(project_id)
            doc_ref = db_firestore.collection('Queries_without_response').document(request_args["user_id"])
            doc = doc_ref.get()
            if doc.exists:
                doc_ref.update({"queries": firestore.ArrayUnion([query])})
            else:
                doc_ref.set({"queries": [query]}, merge=True)
            
            return create_response(ans, 200, request.method)
        else:
            return create_response(ans, 200, request.method)
    else:
        if query_type == "request_for_assessment_in_query":
            ans["summary"] = summary
        return create_response(ans, 200, request.method)


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
                "chunk_id": kwargs.get('chunk_id', ''),
                "content_id": kwargs.get('videoId', ''),
                "video_id": "JWplayer", 
                "title": kwargs.get('videoName', ''), 
                "type": "video", 
                "video_start_position": kwargs.get('timeStamp', ''), 
                "description_short": kwargs.get('text', ''), 
                "description": kwargs.get('speechTranscription', ''),
                "score": kwargs.get('score', '')}
        # If singleSummary is False, include only full description in the item.
        return {
                "chunk_id": kwargs.get('chunk_id', ''),
                "content_id": kwargs.get('videoId', ''),
                "video_id": "JWplayer", 
                "title": kwargs.get('videoName', ''), 
                "type": "video", 
                "video_start_position": kwargs.get('timeStamp', ''), 
                "description": kwargs.get('speechTranscription', ''),
                "score": kwargs.get('score', '')}
    
    else:
        if singleSummary:
            return {
                    "chunk_id": kwargs.get('chunk_id', ''),
                    "content_id": kwargs.get('contentId', ''), 
                    "title": kwargs.get('docName', ''), 
                    "type": "document", 
                    "description_short": kwargs.get('text', ''), 
                    "description": kwargs.get('originalText', ''),
                    "score": kwargs.get('score', '')}
        
        return {
                "chunk_id": kwargs.get('chunk_id', ''),
                "content_id": kwargs.get('contentId', ''), 
                "title": kwargs.get('docName', ''), 
                "type": "document", 
                "description": kwargs.get('originalText', ''),
                "score": kwargs.get('score', '')}


def create_embedding(article):
    """
    Creates an embedding vector for a given article using the OpenAI text-embedding-ada-002 model.
    
    article: str, input text article.
    return: list, the embedding vector for the input article.
    """
    return client.embeddings.create(input = [article], model="text-embedding-3-large").data[0].embedding



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
    # Initialize the Text Generation 
    # text_model = TextGenerationModel.from_pretrained("text-bison@001")
    # to store the final results
    query = kwargs.get("query", "query sent")
    number = kwargs.get("number", 10)
    query_source = kwargs.get("query_source", None)
    query_type = kwargs.get("query_type", None)
    ans = {"metadata":{"query": query, "type": type, "number": number, "class": "content"}, "results":[]}
    # Define the prompt for the Text Generation Model
    # prompt = f"""Check whether the query is or contain questions. If so, using below content answer them. If not, summarize below content according to the query ---: Query: {query}; \n Content:{content}"""
    try:
        if "lc" in query:
            query = query.replace(" lc", " live clinic")
            query = query.replace("lc ", "live clinic ")
            query = query.replace(" lc ", " live clinic ")
            if query == "lc":
                query = "live clinic"
        query_vector = create_embedding(query)
        # query_vector = create_embedding(kwargs.get("query", ""))
    except Exception as e: 
        print(e)
        logger.error(e)
        return create_response("The embedding model quota is exceeding, please check logs for more details.", 400, "get")
    

    if query_type == "single_live_clinic":
        ans["metadata"]["class"] = "live clinic"
        logger.info("Search specific materials")
        if "lc" in query_source.lower():
            query_source = query_source.lower()
            query_source = query_source.replace("lc", "Live Clinic")
        search_response = index.query(
                top_k=kwargs.get("number", 30),
                vector=query_vector,
                filter={
                    "videoName": {"$eq": query_source},
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                },
                namespace='ics-ai-test',
                include_metadata=True)
        
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            score = item['score']
            videoId = item['metadata']['videoId']
            videoName = item['metadata']['videoName']
            timeStamp = item['metadata']['startTimeSeconds']
            stage = item['metadata']['stage']
            speechTranscription = item['metadata']['speechTranscription']
            chunk_id = item["metadata"]["chunk_id"]
            if kwargs.get("singleSummary", False):
                response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                text = response.text
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
            else:
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
    elif query_type == "all_live_clinic":
        ans["metadata"]["class"] = "live clinic"
        logger.info("Search all relevant materials")
        search_response = index.query(
                top_k=kwargs.get("number", 30),
                vector=query_vector,
                filter={
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                },
                namespace='ics-ai-test-liveclinics',
                include_metadata=True)
        
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            score = item['score']
            videoId = item['metadata']['videoId']
            videoName = item['metadata']['videoName']
            timeStamp = item['metadata']['startTimeSeconds']
            stage = item['metadata']['stage']
            speechTranscription = item['metadata']['speechTranscription']
            chunk_id = item["metadata"]["chunk_id"]
            if kwargs.get("singleSummary", False):
                response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                text = response.text
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
            else:
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                           videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
        
        fuzz_results = fuzzy_keyword_search(query, ALL_LC_CHUNKS,  kwargs.get("user_stage_nvalue", 0))
        if len(fuzz_results) > 0:
            existed_chunk_id_list = [item["chunk_id"] for item in ans["results"]]
            i = 0
            for fr in fuzz_results:
                if i > 9:
                    break
                if fr[0]['metadata']['chunk_id'] in existed_chunk_id_list:
                    continue
                ans["results"].append(create_item(fr[0]['metadata']['type'], False, videoId=fr[0]['metadata']['videoId'], 
                                                videoName=fr[0]['metadata']['videoName'], stage=fr[0]['metadata']['stage'], timeStamp=fr[0]['metadata']['startTimeSeconds'], speechTranscription=fr[0]['metadata']['speechTranscription'], score=fr[0]['score'], chunk_id=fr[0]['metadata']['chunk_id']))
                i += 1

    elif query_type == "request_for_assessment_in_query":
        ans["metadata"]["class"] = "evaluation"
        logger.info("user's query is not supported")
        return ans, "Please try a new query. If you are asking for evaluation or feedback, please submit your work first; If you have any issues with your feedback, Please contact coach for further help."

    elif query_type == "query_FAQ":
        ans["metadata"]["class"] = "support"
        logger.info("Search all relevant materials in FAQ database")
        search_response = index.query(
                top_k=kwargs.get("number", 20),
                vector=query_vector,
                filter={
                    "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                },
                namespace='ics-ai-test-faq',
                include_metadata=True)
        
        for item in search_response['matches']:
            # Filtering out items based on score threshold
            score = item['score']
            if item['score']< kwargs.get("thres", ""):
                continue
            originalText = item["metadata"]["originalText"]
            docName = item["metadata"]["docName"]
            stage = item["metadata"]["stage"]
            contentId = item["metadata"]["contentId"]
            chunk_id = item["metadata"]["chunk_id"]
            if kwargs.get("singleSummary", False):
                response = text_model.predict(prompt=prompt.format(originalText), temperature=0.2)
                text = response.text
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                        docName=docName, stage=stage, text=text, originalText=originalText, score=score, chunk_id=chunk_id))
            else:
                ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                        docName=docName, stage=stage, originalText=originalText, score=score, chunk_id=chunk_id))

    else:
        if type == "document":
            logger.info("type is document")

            search_response = index.query(
                    top_k=kwargs.get("number", 20),
                    vector=query_vector,
                    filter={
                        "type": {"$eq": type},
                        "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                    },
                    namespace='ics-ai-test',
                    include_metadata=True)
            for item in search_response['matches']:
                # Filtering out items based on score threshold
                score = item['score']
                if item['score']< kwargs.get("thres", ""):
                    continue
                originalText = item["metadata"]["originalText"]
                docName = item["metadata"]["docName"]
                stage = item["metadata"]["stage"]
                contentId = item["metadata"]["contentId"]
                chunk_id = item["metadata"]["chunk_id"]
                if kwargs.get("singleSummary", False):
                    response = text_model.predict(prompt=prompt.format(originalText), temperature=0.2)
                    text = response.text
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                            docName=docName, stage=stage, text=text, originalText=originalText, score=score, chunk_id=chunk_id))
                else:
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                            docName=docName, stage=stage, originalText=originalText, score=score, chunk_id=chunk_id))
        
        elif type == "video":
            logger.info("type is video")

            search_response = index.query(
                    top_k=kwargs.get("number", 10),
                    vector=query_vector,
                    filter={
                        "type": {"$eq": type},
                        "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                    },
                    namespace='ics-ai-test',
                    include_metadata=True)
            for item in search_response['matches']:
                # Filtering out items based on score threshold
                score = item['score']
                if score< kwargs.get("thres", 0):
                    continue
                videoId = item['metadata']['videoId']
                videoName = item['metadata']['videoName']
                timeStamp = item['metadata']['startTimeSeconds']
                stage = item['metadata']['stage']
                speechTranscription = item['metadata']['speechTranscription']
                chunk_id = item["metadata"]["chunk_id"]
                if kwargs.get("singleSummary", False):
                    response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                    text = response.text
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                            videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
                else:
                    ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                            videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription, score=score, chunk_id=chunk_id))
        
        elif type == "all":
            logger.info("type is all")
            
            search_response = index.query(
                    top_k=kwargs.get("number", 0),
                    vector=query_vector,
                    filter = {
                        "type": {"$in":["document","video"]},
                        "stage": {"$lte": kwargs.get("user_stage_nvalue", 0)}
                        },
                    namespace='ics-ai-test',
                    include_metadata=True )
            for item in search_response['matches']:
                # Filtering out items based on score threshold
                score = item['score']
                if item['score']< kwargs.get("thres", 0):
                    continue
                if item['metadata']['type'] == 'video':
                    videoId = item['metadata']['videoId']
                    videoName = item['metadata']['videoName']
                    timeStamp = item['metadata']['startTimeSeconds']
                    stage = item['metadata']['stage']
                    speechTranscription = item['metadata']['speechTranscription']
                    chunk_id = item["metadata"]["chunk_id"]
                    if kwargs.get("singleSummary", False):
                        response = text_model.predict(prompt=prompt.format(speechTranscription), temperature=0.2)
                        text = response.text
                        ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                            videoName=videoName, stage=stage, timeStamp=timeStamp, text=text, speechTranscription=speechTranscription, score=score,chunk_id=chunk_id))

                    else:
                        ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), videoId=videoId, 
                                            videoName=videoName, stage=stage, timeStamp=timeStamp, speechTranscription=speechTranscription, score=score,chunk_id=chunk_id))

                elif item['metadata']['type'] == 'document':
                    originalText = item["metadata"]["originalText"]
                    docName = item["metadata"]["docName"]
                    stage = item["metadata"]["stage"]
                    contentId = item["metadata"]["contentId"]
                    chunk_id = item["metadata"]["chunk_id"]
                    if kwargs.get("singleSummary", False):
                        response = text_model.predict(prompt=prompt.format(originalText), temperature=0.2)
                        text = response.text
                        ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                            docName=docName, stage=stage, text=text, originalText=originalText, score=score, chunk_id=chunk_id))
                    else:
                        ans["results"].append(create_item(item['metadata']['type'], kwargs.get("singleSummary", False), contentId=contentId, 
                                            docName=docName, stage=stage, originalText=originalText, score=score, chunk_id=chunk_id))
    

        else:
            logger.info("type is others")
            return "Type must be all, video or document", None
        # Filter the existed item
        fuzz_results = fuzzy_keyword_search(query, ALL_CHUNKS,  kwargs.get("user_stage_nvalue", 0))
        if len(fuzz_results) > 0:
            existed_chunk_id_list = [item["chunk_id"] for item in ans["results"]]
            i = 0
            for fr in fuzz_results:
                if i > 9:
                    break
                if fr[0]['metadata']['chunk_id'] in existed_chunk_id_list:
                    continue
                ans["results"].append(create_item(fr[0]['metadata']['type'], False, contentId=fr[0]['metadata']['contentId'], 
                                                docName=fr[0]['metadata']['docName'], stage=fr[0]['metadata']['stage'], originalText=fr[0]['metadata']['originalText'], score=fr[0]['score'], chunk_id=fr[0]['metadata']['chunk_id']))
                i += 1
        
    ans["results"] = remove_key_from_dicts(ans["results"], "chunk_id")
    ans["metadata"]["number"] = len(ans["results"])
    if kwargs.get("allSummary", False):
        all_text = ""
        results = ans["results"]
        # logger.info("input -")
        logging.info(f"results: {results}")
        results_copy = {str(index + 1): item for index, item in enumerate(results)}

        keywords_with_definitions = {"PB": "Personal best", "BEDS-M": "An acronym for improving focus and reducing procrastination, based on behavioural science research. It stands for Burnt ships, Environmental optimisation, Distraction cheat sheet, scheduling, and minimum viable goals. Further information is available in the lessons around intermediate procrastination techniques.",
"microlearning": "Microlearning, or micro-learning, when learning happens in short discrete bursts of learning, rather than long continuous study sessions. Entire systems of learning can be built around microlearning.""",
                             "Kolbs":"Kolbs, or Kolb’s is short for Kolb’s experiential learning cycle, which is a framework for reflective practice developed by David Kolb. We teach a modified and much more detailed and practically nuanced version of Kolb’s that is ideal for accelerating skill development. This is taught from the Briefing stage onwards and is a core part of the system we teach.",
                             "TLS": "Traffic Light System. This is a unique inquiry-based learning system that is taught in the program in the Technique Training stage. It focuses on developing early relational learning and higher-order information evaluation which can be built on later with the BHS (Bear Hunter System)",
                             "CSP": "Cognitive Switching Penalty",
                             "GRINDE": "GRINDE is an acronym for developing mindmaps that is taught in the Ascent 3 stage.",
                             "BHS": "Bear Hunter System - our novel higher-order, high-efficiency encoding system that leverages inquiry-based learning, cognitive load management, and relational non-linear note-taking. It is taught across Ascent 1, Ascent 2, and Ascent 3 stages.",
                             "Hipshot": "A more advanced version of the BHS which combines the Aim and Shoot step of the BHS. This is only possible when a level of unconscious competence has been reached for Aim and Shoot.",
                             "Aim step": "The first step of the Bear Hunter System which primes the brain using inquiry-based learning principles, layering, and priming. Taught in Ascent 1.",
                             "Shoot step": "The second step of the Bear Hunter System which engages in elaborative learning and deeper information gathering and evaluation. This is paired with a non-linear note-taking step. Taught in Ascent 2.",
                             "Skin step": "The third and final step of the Bear Hunter System which encourages higher-order evaluation of an existing generated network of information. It emphasises prioritisation, spatial arrangement, and more critical decision making of importance. Taught in Ascent 3.",
                             "Importance-based chunking": "A method of chunking that priorities creating relationships based on similarities of reasons for importance. It is a method of higher-order evaluation which tends to result in higher quality mental model and schema formation. This is developed in Ascent 1 but is sometimes referred to superficially in earlier stages.",
                             "PEER-peer": "A method of behavioural change taught in the Base Camp stage which can be used for reducing procrastination or habit formation. It stands for Prep, Easy, Exit, Reward, and peer (for accountability peer).",
                             "OFF-rest": "OFF-rest timing stands for Optimised for Focus rest timing which a method of work-rest timing that optimises deep work through timed, variable work sessions followed by strategic usage of break times.",
                             "WPW": "Whole Part Whole teaching - an adaptation of an existing framework for teaching which can be used as a form of interleaved retrieval at multiple orders.",
                             "Parkinson's law": "A widely known phenomenon that suggests that work expands or contracts to fill the time allocated to it.",
                             "Multi-pass": "Multi-pass, or multipass, is a layered system of learning which describes a chronology of how study sessions can be structured to learn effectively. During a multipass session, techniques such as BHS can be utilised. This is taught in Summit. This can also be used for cramming.",
                             "MR FIG": "This is an acronym which for helping to improve attention to detail and performance during pressure situations. It is taught during Summit. It stands for Mirror calibration, Ritual, Focus training, Image training, Graduated exposure.",
                             "V-ABC": "A framework of behavioural change based on behavioural science. It stands for vulnerability factors, antecedents, behaviour, and consequence.",
                             "Rule of 3": "An active flashcard management system that allows learners to get the most out of flashcard applications utilising spaced repetition and active recall.",
                             "Modified method of loci": "A modification of the popular method of loci memorisation method which is adapted for incorporation into non-linear freehand note-taking. It reduces the dependency on an imagined physical space, or sequential linking of elements in the link method of memorisation.",
                             "Mindmap": "A relational non-linear form of note-taking.",
                             "VP-ReF-RE": "A checklist for evaluating the quality of a mindmap. Taught in Ascent 2.",
                             "Priority 0+1": "A highly effective and time-efficient method of prioritisation we teach which is based on a combination of existing and popular prioritisation frameworks and relevant research.",
                             "Positional decision making": "A method of decision-making which is based on putting the person in the best position to make cascading positive EV (expected value) decisions, based on having more information to judge the magnitude and probability of benefits and risks. Unlike traditional decision-making, positional decision-making does not require the person to understand the outcome, but rather is a process driven decision that assumes the best outcome results from putting ourselves in continuously more positive expected value situations where opportunities and available information are greater.",
                             "Outcome as experience": "Outcome as experience is a common mistake in Kolb's experiential learning cycle. It occurs when you reflect on an outcome rather than a process, making it difficult to make productive adjustments.",
                             "Brief Reflection": "If your reflection is too short, there is insufficient information to analyse in the abstraction step.",
                             "Superficial reflection": "Although there is sufficient information, that information is not metacognitive enough to gain meaningful insights into the process.",
                             "Theoretical abstraction": "Instead of analysing the information in the reflection, the abstraction is based on your own “ideas”, which could be influenced by biases.",
                             "Reflection as abstraction": "Instead of analysing the information in the reflection, the abstraction is simply an extension of the reflection.",
                             "Experiment overload": "This happens when there are too many experiments in one cycle.",
                             "Intention experimentation": "This happens when experiments are about “putting in more effort” rather than something specific or actionable.",
                             "Random experimentation": "This happens when experiments are not connected to the findings from the abstraction.",
                             "Non-cyclical Kolb’s": "This happens when experiments do not carry forward as the experience in the next Kolb’s."
                            }

        print("query")
        # query = query_reconstruction(query)
        if query_type == "single_live_clinic":
            PROMPT = f"""
                    query: {query}
                    content dictonary: {results_copy}
                    Key words: {keywords_with_definitions}

                    Hints: lc is the acronym of live clinic. In query, Either lc or clinic refer to live clinic.

                    Perform one task based on the query.
                    1. all items in the content dictionary are part of the document titles that exactly match the query. Utilize all chunks to provide the most accurate response to the user's query.

                    Your output must be structured in JSON format, with the generated answer under the key 'answer_or_summary'.
                    Example of expected output format:
                    {{
                    "answer_or_summary": ""
                    }}
            """

        else:
            PROMPT = f"""
                        query: {query}
                        content dictonary: {results_copy}
                        Key words: {keywords_with_definitions}

                            Perform two tasks based on the query:
                            1. Generate a short and precise answer to the query according to the items in the content dictonary and relevant keywords definition if keywords appear in query or content dictionary, ensuring the explanation is thorough and informative. If you cannot generate answer, generate a detailed summary of the relevant contents to the keywords in query.
                            2. Filter the content list to include only items relevant to the query, keep the key of the items in the content dictonary that are relevant to the question.

                            Requirements: 
                            1. The answer must based on the information from content dictionary and keyword definition, Don't use completely generic information. If you found there's no answer or summary direct to the query, but there's other relevant information to some keywords in the query, Just generate the detailed and precise response based on other relevant information.
                            2. If answer contains sources, use title of the items instead of key of the items.
                            3. The filtered content list should be returned as an array, which only contain the relevant index list.

                            Your output must be structured in JSON format, with the generated answer under the key 'answer_or_summary' and the filtered content list under the key 'filtered_content_list'.

                            Example of expected output format:
                            {{
                            "answer_or_summary": "",
                            "filtered_content_list": ["1","2","4"]
                            }}
                            """
        #try:
        parser = JsonOutputParser()
        messages = [
            SystemMessage(
                content="You are a professional assistant, skilled in extract relevant information from context to answer query. You always answer query short but precise"
            ),
            HumanMessage(
                content=f"{PROMPT}"
            ),
        ]
        # llm = ChatGoogleGenerativeAI(model="gemini-pro",
        #                             temperature=0.0, convert_system_message_to_human=True,safety_settings={
        #         HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        #         HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        #     })

        llm = ChatOpenAI(model_name = "gpt-4-turbo-preview", frequency_penalty = 1,temperature = 0.2, top_p = 0.3, openai_api_key="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")
        chain =  llm | parser
        response = chain.invoke(messages) 
        if query_type == "single_live_clinic":
            filtered_results = ans["results"]
        else:
            filtered_content_list = response['filtered_content_list']
            filtered_results = [results_copy[str(key)] for key in filtered_content_list]

        logging.info(f"ai_response: {response}")

        content = filtered_results
        ans["results"] = content
        if "answer_or_summary" in response:
            answer_from_AI = response.get("answer_or_summary", "")
        if "answer" in response:
            answer_from_AI = response.get("answer", "")
        if len(content) == 0:
            answer_from_AI = "There are no relevant materials at the moment. Please try a new query."
        #except Exception as error:
        # print(error)
        # logging.info(f"Error: {error}")
        # answer_from_AI = "There are no relevant materials at the moment. Please try a new query."
        
        
        # response = text_model.predict(prompt=prompt.format(query=query, content=all_text), temperature=0.2)
        # summary = response.text
        ans["metadata"]["number"] = len(ans["results"])

        return ans, answer_from_AI
    return ans, "empty"


def fuzzy_keyword_search(query, chunks, stage, threshold=75):
    """
    Performs a fuzzy keyword search to find matches in a list of enumerations based on the given query.
    This function iterates through each enumeration, extracting the 'heading' field (if present and non-empty),
    and compares it against the query using fuzzy string matching. Enumerations are considered a match if
    the similarity score meets or exceeds the specified threshold.
    Args:
        query (str): The search query used for matching against the enumeration headings.
        enumerations (list of dicts): A list of dictionaries, where each dictionary represents an enumeration
                                      and contains at least a 'heading' key.
        threshold (int, optional): The minimum similarity score (0-100) for a match to be considered valid.
                                   Defaults to 75.
    Returns:
        list of tuples: Each tuple contains the matched enumeration and its corresponding similarity score.
                        The format is [(matched_enumeration_dict, score), ...].
    Note:
        The function uses fuzz.token_set_ratio from the fuzzywuzzy library for calculating similarity scores.
    """
    matches = []
    # Check if the heading matches the query significantly
    for chunk in chunks:
        if chunk["metadata"]["stage"] > stage:
            continue

        if "speechTranscription" in chunk["metadata"]:
            heading_score = fuzz.token_set_ratio(query, chunk["metadata"]["speechTranscription"])
        if "originalText" in chunk["metadata"]:
            heading_score = fuzz.token_set_ratio(query, chunk["metadata"]["originalText"])
        if heading_score >= threshold:
            matches.append((chunk, heading_score))
    return matches

def remove_key_from_dicts(list_of_dicts, key_to_remove):
    for dictionary in list_of_dicts:
        dictionary.pop(key_to_remove, None)
    return list_of_dicts


def get_embedding(text: str = "What is life?") -> list:
    """Text embedding with a Large Language Model."""
    model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    embeddings = model.get_embeddings([text])
    vector = embeddings[0].values
    print(f"Length of Embedding Vector: {len(vector)}")
    return vector

def query_reconstruction(text: str) -> str:
    prompt = f"""
        Your task is improving user's input query. Add punctuation or correct the common words in the query. 

        query: {text}

        Your output must be structured in JSON format, with the generated query under the key 'generated_query'.

        Example of expected output format:
        {{
        "generated_query": ""
        }}
    """
    parser = JsonOutputParser()
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=(
                    prompt
                )
            ),
            HumanMessagePromptTemplate.from_template("{text}"),
        ]
    )

    chat_message =  chat_template.format_messages(text="")
    llm = ChatGoogleGenerativeAI(model="gemini-pro",
                                temperature=0.0, convert_system_message_to_human=True,safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        })
    chain =  llm | parser
    response = chain.invoke(chat_message)

    return response["generated_query"]


def query_classier(query: str) -> str:

    class_1 = "all_live_clinic"
    class_2 = "single_live_clinic"
    class_3 = "general_query"
    class_4 = "request_for_assessment_in_query"
    class_5 = "query_FAQ"
    llm = ChatOpenAI(model_name = "gpt-4-turbo-preview", frequency_penalty = 1,temperature = 0, openai_api_key="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")
    parser = JsonOutputParser()
    query_classier_prompt = memory_prompt.query_classifier_prompt
    chain = query_classier_prompt | llm | parser
    user_input = f""" "{query}" \n Please help me classify this query into the classes below. \n classes: [{class_1}, {class_2}, {class_3}, {class_4}, {class_5}], if the query is single_live_clinic, extract the source name from query. Your output should be valid json. \n example output {{"label": class, "source": source}} """

    response = chain.invoke({"input": user_input})
    return response

