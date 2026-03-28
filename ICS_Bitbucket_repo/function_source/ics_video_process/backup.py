import functions_framework
from google.cloud import storage, videointelligence
import json
import asyncio
from gcp import *

logger = gcp_logger()
project_id = gcp_project_id()

# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def main(cloud_event):
    # trigger the bucket to get the uploaded file
    data = cloud_event.data
    video_name = data['name']
    logger.debug(f"Processing file: {video_name}.")
    # check the uploaded file is a video
    # .mov, .mpeg4, .mp4, .avi are the valid types
    valid_types = ["mov","mpeg4","mp4","avi"]
    file_type = video_name.split(".")[-1]
    if file_type not in valid_types:
        return "No valid video uploaded, exit."

    # generate the video uri
    bucket_name = data['bucket']
    path = f"gs://{bucket_name}/{video_name}"
    
    # extract video transcript with a shorter timeout
    asyncio.run(async_video_process(video_name, path))

    return ("OK", 200)

async def async_video_process(video_name, path, timeout=30):
    # shoter timeout to avoid timeout error
    logger.debug("Start running time track")
    try:
        async with asyncio.timeout(timeout):
            # run the extraction function in an async method
            await speech_transcription(video_name, path)
    except TimeoutError:
        logger.debug("The long operation timed out, but we've handled it.")
    
async def speech_transcription(video_name, path, lang="en"):
    # default settings
    video_client = videointelligence.VideoIntelligenceServiceClient()
    features = [videointelligence.Feature.SPEECH_TRANSCRIPTION]
    config = videointelligence.SpeechTranscriptionConfig(
        language_code=lang,
        enable_automatic_punctuation=True
    )
    video_context = videointelligence.VideoContext(speech_transcription_config=config)

    # generate the transcript file name with the video name
    # object_id = video_name.replace(".mp4",".json")
    object_id = video_name.split(".")[0] + ".json"
    target_bucket = f"{project_id}-video-transcription"
    # add the "output_uri" to store transcript in the bucket
    operation = video_client.annotate_video(
        request={
            "features": features,
            "input_uri": path,
            "video_context": video_context,
            "output_uri": f"gs://{target_bucket}/{object_id}",
        }
    )
    logger.debug("\nProcessing video for speech transcription.")
    result = operation.result(timeout=3600)
    # add the sleep to yield control back to the event loop temporarily
    await asyncio.sleep(0)

    logger.debug("video is processed.")
    annotation_results = result.annotation_results[0]
    transcriptions = []
    for speech_transcription in annotation_results.speech_transcriptions:
        # use the transcript with the highest confidence
        transcription = speech_transcription.alternatives[0].transcript
        transcriptions.append({"speech_transcriptions":transcription})

    logger.debug(transcriptions)