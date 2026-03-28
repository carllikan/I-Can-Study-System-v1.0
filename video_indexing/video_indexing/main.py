from google.cloud import storage, videointelligence
from firebase_admin import firestore
import json
import openai
import knn_tags
from flask import Flask, request


app = Flask(__name__)

# main funtion
@app.route("/", methods=["POST"])
def main():
    """Triggered by a change to a Cloud Storage bucket.
    Args:
        event (dict): Event payload.
        context (google.cloud.functions.Context): Metadata for the event.
    """
    # http get the uploaded file
    request_json = request.get_json()
    if not request_json:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400
    video_name = request_json.get("file","")
    print(f"Processing file: {video_name}.")

    # check the uploaded file is a video
    if ".mp4" not in video_name:
        return "No video uploaded, exit."

    # generate the video uri
    bucket_name = "video-analysis-brett"
    path = f"gs://{bucket_name}/{video_name}"

    # extract the video transcription
    transcriptions = extract_video_transcription(path, "en")
    # generate the video transcription embeddings
    video_transcriptions = transcription_embedding(transcriptions)
    # generate the video tags based on transcription
    video_tags = generate_tags(transcriptions)

    # store the video information into the Firestore databse
    store_video_info(video_name, path, video_transcriptions, video_tags)
     
    return "OK", 200

# transcription extract function
def extract_video_transcription(path, lang):
    # default settings
    video_client = videointelligence.VideoIntelligenceServiceClient()
    features = [videointelligence.Feature.SPEECH_TRANSCRIPTION]
    config = videointelligence.SpeechTranscriptionConfig(
        language_code=lang,
        enable_automatic_punctuation=True
    )
    video_context = videointelligence.VideoContext(speech_transcription_config=config)

    operation = video_client.annotate_video(
        request={
            "features": features,
            "input_uri": path,
            "video_context": video_context,
        }
    )
    print("\nProcessing video for speech transcription.")
    result = operation.result(timeout=600)

    # There is only one annotation_result since only
    # one video is processed.
    annotation_results = result.annotation_results[0]
    transcriptions = []
    for speech_transcription in annotation_results.speech_transcriptions:
        # use the transcript with the highest confidence
        transcription = speech_transcription.alternatives[0].transcript
        transcriptions.append({"speech_transcriptions":transcription})
    print(transcriptions)
    return transcriptions

# store the information in Firestore
def store_video_info(video_name, video_uri, transcriptions, tags):
    import uuid

    # use uuid as the video id
    db = firestore.Client()
    video_id = str( uuid.uuid4() )
    video_info = {"video_id":video_id, "video_name":video_name, "video_uri":video_uri, "transcriptions":transcriptions, "tags":tags}
    
    # store the video information into the Firestore with the video id as document id
    db.collection('ics_videos').document(video_id).set(video_info)
    print(f"video {video_id} information stored")

# transcription ecoding function     
def transcription_embedding(my_dict_list):
    key_to_find = 'speech_transcriptions'
    openai.api_key = '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'
    embedding_model = "text-embedding-ada-002"
    # call function to split and encoding sentences
    for i in range(len(my_dict_list)):
        key_list = list(my_dict_list[i].keys())
        index_of_key = key_list.index(key_to_find)
        sentence = my_dict_list[i].get(key_list[index_of_key])
        embedding = get_embedding(sentence, engine=embedding_model)
        my_dict_list[i]['sentence_embedding'] = embedding
    # print(f"embeddings: {embeddings}")
    return my_dict_list

# define openai encoding function
def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   return openai.Embedding.create(input = [text], model=model)['data'][0]['embedding']

# ganerate the video tags by a given tags list
def generate_tags(transcriptions):
    # get the full video transcription content
    sum_trans = ""
    for item in transcriptions:
        sum_trans = sum_trans + item['speech_transcriptions']
    print(f"all transcription: {sum_trans}")
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
    print(f"generate tags: {generate_tags}")

    return generate_tags