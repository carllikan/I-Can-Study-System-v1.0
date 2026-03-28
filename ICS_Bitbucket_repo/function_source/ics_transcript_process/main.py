import functions_framework
from google.cloud import storage
from firebase_admin import firestore
import json
import openai
import knn_tags
import pinecone
from datetime import datetime
from gcp import *

logger = gcp_logger()
func_conf = gcp_get_config()
project_id = gcp_project_id()

# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def main(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    transcript_file = data["name"]

    print(f"Processing file: {transcript_file}.")
    # check the uploaded file is a json
    if ".json" not in transcript_file:
        return ("No valid transcription JSON file uploaded, exit", 400)

    # extract the json content from the file
    content_json = read_content(bucket_name, transcript_file)
    if not content_json:
        return ("No required content in the transcript json file, exit", 400)

    # Process the JSON file
    video_info = content_json.get("results", [])
    if not video_info:
        return ("No required content in the transcript json file, exit", 400)
    # only one video is processed
    results = video_info
    video_name = data["name"].split("_transcript_")[0]
    video_path = f"gs://{project_id}-search-videos/{video_name}.mp4"

    video_bucket = f"{project_id}-search-videos"
    print (f"The uri of the video is {video_path}")

    # get metadata file path
    video_type = video_path.split(".")[-1]
    meta_name = video_name + '.json'
    meta_json = read_content(video_bucket, meta_name)
    if not meta_json:
        print("Metadata Json not ready")
        return
    # extract transcripts and thier start time
    transcriptions = []
    for result in results:
        alternatives = result.get('alternatives', [])
        if not alternatives:
            print ("no transcriptions")
            return ("no transcriptions", 200)
        # use the transcript with the highest confidence
        transcription = alternatives[0].get('transcript', '')
        if not transcription:
            print ("no transcriptions")
            return ("no transcriptions", 200)
        # use the start time for the first word in the transcript
        start_time_seconds = alternatives[0].get('words', [])[0].get('startOffset', '0s')
        transcriptions.append({"speech_transcriptions":transcription, "start_time_seconds": start_time_seconds})

    # check if the video is empty
    if not transcriptions:
        print ("no transcriptions")
        return ("no transcriptions", 200)

    print(transcriptions)

    # generate the video transcription embeddings
    video_transcriptions = transcription_embedding(transcriptions)
    # generate the video tags based on transcription
    video_tags = generate_tags(transcriptions)

    # store the video information into the Firestore databse
    # store_video_info(transcript_file, video_name, path, video_transcriptions, video_tags)

    # store the video information into the Pinecone databse
    store_to_pinecone(video_name, video_transcriptions, video_path, video_tags, meta_json)

    return ("ok", 200)

def read_content(bucket_name, file_name):
    # Instantiate the Cloud Storage client
    storage_client = storage.Client()
    # Retrieve the file from Cloud Storage
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Read the file contents as a JSON object
    try:
        file_contents = blob.download_as_text()
        data_json = json.loads(file_contents)
    except Exception as e:
        logger.debug(f"Got an error when read the json file: {file_name}")
        return {}

    return data_json

def store_to_pinecone(video_name, transcriptions, video_uri, tags, meta_json):
    import uuid
    video_id = str( uuid.uuid4() )
    # retrieve variables from firestore
    project_number = gcp_project_number(project_id)
    pinecone_api = gcp_get_secret(project_number,func_conf.get( 'pinecone_api_key', 'pinecone_api_key_name' ))
    pinecone_env = func_conf.get( 'pinecone_env', 'eu-west4-gcp' )

    pinecone.init(api_key=pinecone_api, environment=pinecone_env)
    pine_index = func_conf.get( 'pinecone_index', 'gen-search-embedding')
    index = pinecone.Index(pine_index)
    pinecone_vectors = []
    now = datetime.now()
    date_time = now.strftime("%Y-%m-%d %H:%M:%S")
    for i in range(len(transcriptions)):
        p_id = video_id + '_' + str(i)
        # add metadata into the transcription records
        trans_json = {"videoId":video_id, "videoName":video_name, "videoUri":video_uri, "type": "video", "videoTags": tags,"speechTranscription": transcriptions[i]['speech_transcriptions'],'startTimeSeconds': transcriptions[i]['start_time_seconds'], 'processedTimestamp': date_time}
        for key in meta_json.keys():
            trans_json[key] = meta_json[key]
        logger.debug(f"transcription record: {trans_json}")
        pinecone_vectors.append((p_id, transcriptions[i]['sentence_embedding'], trans_json))
        if len(pinecone_vectors) % 100 == 0:
            logger.debug("Upserting batch of 100 vectors...")
            upsert_response = index.upsert(vectors=pinecone_vectors)
            pinecone_vectors = []
    if len(pinecone_vectors) > 0:
        logger.debug("Upserting remaining vectors...")
        upsert_response = index.upsert(vectors=pinecone_vectors)
        pinecone_vectors = []


# transcription ecoding function     
# sentences generate function
def transcription_embedding(my_dict_list):
    import time
    
    project_number = gcp_project_number(project_id)
    openai.api_key = gcp_get_secret(project_number,func_conf.get( 'openai_api_key', 'openai_api_key_name' ))
    # openai.api_key = os.getenv("OPENAI_API_KEY")
    embedding_model = func_conf.get( 'embedding_model', 'text-embedding-ada-002' )
    key_to_find = ['speech_transcriptions', 'start_time_seconds']
    prop_sentence = ''
    prop_sentence_dict_list = []
    i=0
    while (i < len(my_dict_list)-1):
        prop_sentence_dict = {}
        sentence = my_dict_list[i].get(key_to_find[0])
        # get the prop sentence start time.
        prop_sentence_dict['start_time_seconds'] = my_dict_list[i].get(key_to_find[1])
        # if the sentence is over 300 characters feed it to encoding model. 
        # if not, combine sentences until it is over 300 chara and encoding the combined sentence.
        if len(sentence) > 300:
            prop_sentence = sentence.strip()
            embedding = get_embedding(prop_sentence, model=embedding_model)
            i=i+1
        else:
            k=i+1
            while (k < len(my_dict_list)-1):
                sentence = sentence+my_dict_list[k].get(key_to_find[0]).strip()
                k=k+1
                if len(sentence) > 300:
                    break
            prop_sentence = sentence.strip()
            embedding = get_embedding(prop_sentence, model=embedding_model)
            i=k
        # generate new dict list for the prop sentences embedding
        prop_sentence_dict['speech_transcriptions'] = prop_sentence
        prop_sentence_dict['sentence_embedding'] = embedding

        prop_sentence_dict_list = prop_sentence_dict_list + [prop_sentence_dict]
        # sleep 1 second for the openai model rate limit
        time.sleep(1)
    
    # check the last sentence.
    last_sentence = my_dict_list[-1].get(key_to_find[0])
    # if the last sentence is not over 100 character, combine it to the previous combined sentence. 
    # to avoid the duplication with searching key words. 
    if len(last_sentence) < 100:
        last_sentence = prop_sentence.strip() + last_sentence.strip()
        last_embedding = get_embedding(last_sentence, model=embedding_model)
        prop_sentence_dict_list[-1]['speech_transcriptions'] = last_sentence
        prop_sentence_dict_list[-1]['sentence_embedding'] = last_embedding
    else:
        last_embedding = get_embedding(last_sentence, model=embedding_model)
        my_dict_list[-1]['sentence_embedding'] = last_embedding
        prop_sentence_dict_list = prop_sentence_dict_list + [my_dict_list[-1]]
        
    # print(prop_sentence_dict_list)
    return prop_sentence_dict_list

# define openai encoding function
def get_embedding(text, model):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input = [text], model=model)['data'][0]['embedding']

# ganerate the video tags by a given tags list
def generate_tags(transcriptions):
    # get the full video transcription content
    sum_trans = ""
    for item in transcriptions:
        sum_trans = sum_trans + item['speech_transcriptions']
    logger.debug(f"all transcription: {sum_trans}")
    # fake tags list for demo test, will be updated to the given one when in productive
    tags_2d = [
        ['Technology', ['technology', 'computers', 'software']],
        ['Sports', ['football', 'basketball', 'soccer']],
        ['Politics', ['government', 'elections', 'policy']],
        ['Food', ['cooking', 'recipes', 'restaurant']],
        ['Art', ['painting', 'sculpture', 'photography']],
        ['Health', ['fitness', 'nutrition', 'wellness']],
        ['Science', ['physics', 'biology', 'chemistry']],
        ['Business', ['entrepreneurship', 'finance', 'marketing']],
        ['Music', ['musician', 'concert', 'instrument']],
        ['Fashion', ['clothing', 'style', 'design']],
        ['Travel', ['vacation', 'adventure', 'exploration']],
        ['Education', ['learning', 'school', 'knowledge']],
        ['History', ['historical', 'ancient', 'civilization']],
        ['Environment', ['sustainability', 'climate', 'ecology']],
        ['Movies', ['film', 'cinema', 'actor']],
        ['Books', ['novel', 'literature', 'author']],
        ['Fitness', ['exercise', 'workout', 'gym']],
        ['Technology', ['innovation', 'gadgets', 'electronics']],
        ['Science', ['research', 'experiment', 'discovery']],
        ['Business', ['startup', 'management', 'economics']],
    ]
    # call the tags gereration function by comparing the tags list and the full video transcription content
    generate_tags = knn_tags.knn_2(sum_trans, tags_2d, 8)
    logger.debug(f"generate tags: {generate_tags}")

    return generate_tags