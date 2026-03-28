import io
from PIL import Image, ImageFile
from google.cloud import storage
from transformers import AutoModelForObjectDetection, AutoFeatureExtractor
from gcp import *
import base64
from std_response import create_response
from google.cloud import aiplatform
from google.cloud.aiplatform.gapic.schema import predict
import torch
import logging
logger = logging.getLogger()
class MindMapQualityChecker:
    def __init__(self, image_name,bucket_name):
        """
        Initialize the MindMapQualityChecker with the necessary configurations.

        Parameters:
        - image_name (str): Name of the image to be checked.
        - bucket_name (str): Name of the Google Cloud Storage bucket where the image is stored.
        """
        self.image_name = image_name
        self.bucket_name = bucket_name
        # Fetching Google Cloud configurations
        self.project_id = gcp_project_id()
        self.project_number = gcp_project_number(self.project_id)
        self.dev_project_number = '160442880840'
        self.func_conf = gcp_get_config()
        self.location = 'us-central1'
        self.api_endpoint_id = '7787631952328130560'
        # self.api_endpoint_id = self.func_conf.get('mmp_low_clarity_check_endpoint_id', 'mmp_low_clarity_check_endpoint_id_name')
        self.api_endpoint = f'{self.location}-aiplatform.googleapis.com'
        # Hardcoded values for Hugging Face and model checkpoint
        self.HF_ACCESS_TOKEN = gcp_get_secret(self.project_number,self.func_conf.get('hf_access_token', 'hf_access_token_name' ))
        self.model_checkpoint_name = 'AddAxis/detect_screenshot'
            

    def read_image_data_from_gcs(self):
        """
        Read image data from Google Cloud Storage.

        Returns:
        bytes: The image data as a byte stream.
        """
         # Initialize Google Cloud Storage client and get the blob
        client = storage.Client()
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(self.image_name)

        # Download the image data as bytes
        bytes_data = blob.download_as_bytes()
        return bytes_data
    
    def predict_image_clarity(self):
        """
        Make an image classification prediction using Google Cloud's AI Platform.

        Returns:
        bool: True if prediction includes "good", False otherwise.
        """


        logging.info("Start to check image clarity")
        # The AI Platform services require regional API endpoints.
        client_options = {"api_endpoint": self.api_endpoint}
        # Initialize client that will be used to create and send requests.
        # This client only needs to be created once, and can be reused for multiple requests.
        client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
        
        file_content = self.read_image_data_from_gcs()

        # The format of each instance should conform to the deployed model's prediction input schema.
        encoded_content = base64.b64encode(file_content).decode("utf-8")
        instance = predict.instance.ImageClassificationPredictionInstance(
            content=encoded_content,
        ).to_value()
        instances = [instance]
        
        # See gs://google-cloud-aiplatform/schema/predict/params/image_classification_1.0.0.yaml for the format of the parameters.
        parameters = predict.params.ImageClassificationPredictionParams(
            confidence_threshold=0,
            max_predictions=5,
        ).to_value()
        endpoint = client.endpoint_path(
            project=self.dev_project_number, location=self.location, endpoint=self.api_endpoint_id
        )
        try:
            response = client.predict(
                endpoint=endpoint, instances=instances, parameters=parameters
            )

            # See gs://google-cloud-aiplatform/schema/predict/prediction/image_classification_1.0.0.yaml for the format of the predictions.
            predictions = response.predictions

            # Check if any prediction includes "good"
            for prediction in predictions:
                logging.info(f"checking prediction {dict(prediction)}")
                index_good = dict(prediction)['displayNames'].index("good")
                index_bad = dict(prediction)['displayNames'].index("bad")
                if dict(prediction)['confidences'][index_good] > dict(prediction)['confidences'][index_bad]:
                    return True

            return False
        except Exception as e:
            logging.error(e)
            return False
            

    def check_image_size(self):
        """
        Checks if the image size meets the criteria for minimum dimensions (width >= 1024 and height >= 768) and ensures
        the total number of pixels does not exceed a safe limit to avoid decompression bomb DOS attacks.

        Returns:
        bool: True if the image size is within the acceptable range and safe pixel limit, False otherwise.
        """
        # Define a safe pixel limit (e.g., 178956970 pixels)
        logging.info("Start to check image size")
        SAFE_PIXEL_LIMIT = 178956970

       
        bytes_data = self.read_image_data_from_gcs()
        # Temporarily increase the pixel limit to load the image for checking
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            # Open the image directly from bytes data
            with Image.open(io.BytesIO(bytes_data)) as img:
                # Check if the total number of pixels exceeds the safe limit
                if img.width * img.height > SAFE_PIXEL_LIMIT:
                    return False

                return True
        except Image.DecompressionBombError:
            # If a DecompressionBombError is caught, return False
            return False
        finally:
            # Reset the LOAD_TRUNCATED_IMAGES to its default value
            ImageFile.LOAD_TRUNCATED_IMAGES = False

        

    def check_white_background(self):
        """
        Verifies if the image has a white or near-white background by analyzing the predominant color.

        Returns:
        bool: True if the predominant background color is white or near-white, False otherwise.
        """
        
        # Download the image data as bytes
        logging.info("Start to check image background")

        bytes_data = self.read_image_data_from_gcs()

        # Open the image with PIL
        im = Image.open(io.BytesIO(bytes_data))
        try:
            # Ensure image is in an appropriate color space
            if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
                # Fill transparent parts with white
                with Image.new("RGBA", im.size, "WHITE") as base:
                    im = Image.alpha_composite(base, im).convert("RGB")
            else:
                im = im.convert("RGB")

            colors = im.getcolors(im.size[0]*im.size[1])
            max_color = max(colors, key=lambda item: item[0])

            # Adjust color checking logic if needed
            return all(c >= 249 for c in max_color[1])
        except Exception as e:
            logging.info(e)
            return False
    def check_if_screenshot(self):
        """
        Determines if the mind map image is a screenshot using a Hugging Face object detection model.

        Returns:
        tuple: A tuple containing the detection results and a boolean indicating whether the image is identified as a screenshot (True) or not (False).
        """
        logging.info("Start to check image noise")
        image_processor = AutoFeatureExtractor.from_pretrained(self.model_checkpoint_name, token=self.HF_ACCESS_TOKEN)
        model = AutoModelForObjectDetection.from_pretrained(self.model_checkpoint_name, token=self.HF_ACCESS_TOKEN)
        bytes_data = self.read_image_data_from_gcs()
        image_data = io.BytesIO(bytes_data)

        # # Open the image with PIL
        image = Image.open(image_data)
        if image.format == "PNG":
            image = image.convert("RGB") 
        inputs = image_processor(images=image, return_tensors="pt")
        outputs = model(**inputs)
        
        target_sizes = torch.tensor([image.size[::-1]])
        results = image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.3)[0]
        logging.info(f'checking noise detection results {results}')
        if len(results['scores'])>0:
            return True
        else:
            return False

    def check_mind_map_quality(self):
        """
        Check the overall quality of the mind map by running all checks.

        Returns:
        - True if all checks pass, False otherwise.
        """

        try:
            
            if not self.check_image_size():
                return create_response('The image size is over the requirement.','400','POST')
            
            if not self.check_white_background():
                return create_response('The image background is not white. Please upload a white background image.','400','POST')
            
            if not self.predict_image_clarity():
                return create_response('The image is hard to be recognized.','400','POST')
    
            if self.check_if_screenshot():
                ### yolo screen shot return True when it is probably a mind map with screenshot.
                return create_response('The image may include unnessary element. Please upload another one.','400','POST')
            return True
        except Exception as e:
            logger.error(e)
            logging.info(f"got the error:=================== {e}")
            return False