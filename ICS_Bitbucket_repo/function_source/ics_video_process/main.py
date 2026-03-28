import functions_framework
from google.cloud import storage, videointelligence
import json
import asyncio
from gcp import *

from google.api_core.client_options import ClientOptions
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech

from moviepy.editor import VideoFileClip
import os


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

async def async_video_process(video_name, path, timeout=600):
    # shoter timeout to avoid timeout error
    logger.debug("Start running time track")
    try:
        async with asyncio.timeout(timeout):
            # run the extraction function in an async method
            await speech_transcription(video_name, path)
    except TimeoutError:
        logger.debug("The long operation timed out, but we've handled it.")
    
async def speech_transcription(video_name, path, lang="en"):

    download_from_bucket(f"{project_id}-search-videos", video_name)
    print("download complete")
    if os.path.exists(video_name):
        print(f"The file {video_name} exists!")

    else:
        print(f"The file {video_name} does not exist.")
    video = VideoFileClip(video_name)

    print("get video")
    audio = video.audio
    output_audio_filepath = video_name.split('.')[0] + '.mp3'
    audio.write_audiofile(output_audio_filepath, codec='mp3')
    client = storage.Client()
    bucket = client.get_bucket(f'{project_id}-search-videos')
    blob = bucket.blob(output_audio_filepath)
    blob.upload_from_filename(output_audio_filepath)
    video.close()
    audio.close()

    response = transcribe_batch_gcs_input_gcs_output_v2({project_id}, f"gs://{project_id}-search-videos/{output_audio_filepath}", f"gs://{project_id}-video-transcription")

    print(response)


def transcribe_batch_gcs_input_gcs_output_v2(
    project_id: str,
    gcs_uri: str,
    gcs_output_path: str
) -> cloud_speech.BatchRecognizeResults:
    """Transcribes audio from a Google Cloud Storage URI.

    Args:
        project_id: The Google Cloud project ID.
        gcs_uri: The Google Cloud Storage URI.

    Returns:
        The RecognizeResponse.
    """


    # Instantiates a client
    clientOptions = ClientOptions(api_endpoint="europe-west4-speech.googleapis.com")
    client = SpeechClient(client_options=clientOptions)

    # The output path of the transcription result.
    workspace = gcs_output_path

    # The name of the audio file to transcribe:
    # gcs_uri = "gs://ics-analysis-dev-search-videos/audio-files/3-Rushing.mp3"

    # Recognizer resource name:
    name = f"projects/{project_id}/locations/europe-west4/recognizers/_"

    config = cloud_speech.RecognitionConfig(
    auto_decoding_config={},
    model="chirp",
    language_codes=["en-AU"],
    features=cloud_speech.RecognitionFeatures(
    enable_word_time_offsets=True,
    enable_automatic_punctuation=True,
    ),
    )

    output_config = cloud_speech.RecognitionOutputConfig(
    gcs_output_config=cloud_speech.GcsOutputConfig(
        uri=workspace),
    )

    files = [cloud_speech.BatchRecognizeFileMetadata(
        uri=gcs_uri
    )]

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=name, config=config, files=files, recognition_output_config=output_config
    )
    operation = client.batch_recognize(request=request)
    response = operation.result(timeout=3600)
    return response


def download_from_bucket(bucket_name, file_name):
    from google.cloud import storage

    # Initialise a client
    storage_client = storage.Client(project_id)
    # Create a bucket object for our bucket
    bucket = storage_client.get_bucket(bucket_name)
    # Create a blob object from the filepath
    blob = bucket.blob(file_name)
    # Download the file to a destination
    blob.download_to_filename(file_name)