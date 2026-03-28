import pandas as pd
import io
import json
import cv2
import numpy as np
import pandas as pd
import uuid
import boto3
from sklearn.metrics.pairwise import euclidean_distances
from google.cloud import storage
from transformers import AutoImageProcessor, AutoModelForObjectDetection
from PIL import Image
import torch
from dotenv import load_dotenv
load_dotenv()
from gcp import *
from textblob import TextBlob
from determineNodeHierarchy import DetermineNodesHierarchy
from detect_colour import *
logger = gcp_logger()
run_conf = gcp_get_config()
PROJECT = gcp_project_id()
func_conf = gcp_get_config()
project_number = gcp_project_number(PROJECT)
OPENAI_API_KEY = gcp_get_secret(project_number,func_conf.get('openai_api_key', 'openai_api_key_name' ))

AWS_ACCESS_KEY_ID = gcp_get_secret(project_number,func_conf.get('aws_access_key_id', 'aws_access_key_name' ))
AWS_SECRET_ACCESS_KEY = gcp_get_secret(project_number,func_conf.get('aws_secret_access_key', 'aws_secret_access_key_name' ))
HF_ACCESS_TOKEN = gcp_get_secret(project_number,func_conf.get('hf_access_token', 'hf_access_token_namee' ))

class GraphFeatureExtractionPipeline():
    
    def __init__(self, drawing_checkpoint, edge_tip_checkpoint):
        # logger.warning(HF_ACCESS_TOKEN)
        self.drawing_image_processor = AutoImageProcessor.from_pretrained(drawing_checkpoint,use_auth_token =HF_ACCESS_TOKEN)
        self.drawing_model = AutoModelForObjectDetection.from_pretrained(drawing_checkpoint,use_auth_token =HF_ACCESS_TOKEN)
        self.edge_tip_image_processor = AutoImageProcessor.from_pretrained(edge_tip_checkpoint,use_auth_token =HF_ACCESS_TOKEN)
        self.edge_tip_model = AutoModelForObjectDetection.from_pretrained(edge_tip_checkpoint,use_auth_token =HF_ACCESS_TOKEN)
        
    def aws_textract(self,file_prefix,file_name):
        textract_client = boto3.client('textract',
                        aws_access_key_id=AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                        region_name="us-east-1"
                    )
        
        client = storage.Client()

        mind_map_bucket_name = f'{PROJECT}-mindmaps'
        # Define the bucket object
        bucket = client.bucket(mind_map_bucket_name)
        # Define the blob (file) object
        blob = bucket.blob(file_name)

        # Read Image as BytesIO
        image_data = io.BytesIO()
        blob.download_to_file(image_data)
        image_data.seek(0)

        # Analyze Image using Textract
        response = textract_client.analyze_document(
            Document={'Bytes': image_data.read()},
            FeatureTypes=['TABLES']
        )

        # Reference the bucket in GCS where you want to save the JSON
        ocr_data_bucket = client.get_bucket(f'{PROJECT}-mindmaps-ocr-data')

        # Create a new blob (object) in the bucket
        # logger.warning(f"aws_textract: {response}")
        blob = ocr_data_bucket.blob(f'{file_prefix}/analyzeDocResponse.json')
        textract_json_str = json.dumps(response)
        # Upload the JSON string to the blob
        blob.upload_from_string(
            textract_json_str,
            content_type='application/json'
        )
    def get_ocr_data(self,file_prefix):

        '''
        Function to get OCR data from a JSON file.

        Inputs:
            - file_prefix (str): Prefix of the file name in Google Cloud Storage.

        Output:
            - df (pd.DataFrame): DataFrame containing OCR data with the following columns:
                                 - 'text': Text extracted from the OCR.
                                 - 'left': Left position of the text bounding box.
                                 - 'top': Top position of the text bounding box.
                                 - 'right': Right position of the text bounding box.
                                 - 'bottom': Bottom position of the text bounding box.
        '''
  
        # Create a client
        client = storage.Client()

        bucket_name = f'{PROJECT}-mindmaps-ocr-data'
        # Define the bucket object
        bucket = client.bucket(bucket_name)
        file_name = f'{file_prefix}/analyzeDocResponse.json'
        # Define the blob (file) object
        blob = bucket.blob(file_name)

        # Read the bytes of the JSON data from the blob
        bytes_data = blob.download_as_bytes()

        # Create a BytesIO object to work with the bytes data
        bytes_io = io.BytesIO(bytes_data)
        # logger.warning(f"BytesIO: {bytes_io}")
        # Parse the JSON data
        data = json.load(bytes_io)

        nodes = []

        for b in data['Blocks']:
            if b['BlockType'] == 'LINE' and (len(b['Text']) > 2):
                node = {'text': b['Text'], 
                        'left': b['Geometry']['BoundingBox']['Left'], 
                        'top': b['Geometry']['BoundingBox']['Top'],
                        'right': b['Geometry']['BoundingBox']['Left'] + b['Geometry']['BoundingBox']['Width'],
                        'bottom': b['Geometry']['BoundingBox']['Top'] + b['Geometry']['BoundingBox']['Height']}

                nodes.append(node)

        return pd.DataFrame(nodes)
    
    def open_image(self,filename, bucketname):
        '''
        Function to open an image from Google Cloud Storage.

        Inputs:
            - filename (str): Name of the image file in Google Cloud Storage.

        Output:
            - img (np.ndarray): Numpy array representing the image in RGB format.
        '''

        client = storage.Client()

        # bucket_name = f'{PROJECT}-mindmaps'
        bucket_name = bucketname
        # Define the bucket object
        bucket = client.bucket(bucket_name)
        file_name = filename
        # Define the blob (file) object
        blob = bucket.blob(file_name)

        # Read the bytes of the JSON data from the blob
        bytes_data = blob.download_as_bytes()

        # Create a BytesIO object to work with the bytes data
        bytes_io = io.BytesIO(bytes_data)
    
        # Convert BytesIO to NumPy array
        np_arr = np.frombuffer(bytes_io.getvalue(), dtype=np.uint8)

        # Decode the image array using OpenCV
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    def threshold_image(self,image, threshold_value = 200):
        '''
        Function to threshold an image based on a specified threshold value.

        Inputs:
            - image (np.ndarray): Input image in RGB format.
            - threshold_value (int): Threshold value for binarization (default: 200).

        Output:
            - threshold (np.ndarray): Thresholded image.
        '''
    
        img = image.copy()
    
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        mean_tone_value = np.mean(gray)


        if mean_tone_value < 128:

            gray = 255 - gray
            mean_tone_value = np.mean(gray)

        threshold_value = int(mean_tone_value * 0.8)

        _, threshold = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)

        threshold = 1 - (threshold / 255.)

        return threshold
    
    def set_bounding_boxes_in_pixels(self, df, img):
        '''
        Function to convert bounding box coordinates from relative values to pixel values.

        Inputs:
            - df (pd.DataFrame): DataFrame containing bounding box information.
            - img (np.ndarray): Input image.

        Output:
            - df (pd.DataFrame): Updated DataFrame with pixel-based bounding box coordinates.
        '''
        img_height = img.shape[0]
        img_width = img.shape[1]

        # img_height = img.shape[0]
        # img_width = img.shape[1]

        for i, row in df.iterrows():

            df.at[i, 'left']   = int(round(row['left'] * img_width))
            df.at[i, 'right']  = int(round(row['right'] * img_width))
            df.at[i, 'top']    = int(round(row['top'] * img_height))
            df.at[i, 'bottom'] = int(round(row['bottom'] * img_height))

        df['left']   = df['left'].astype(int)
        df['right']  = df['right'].astype(int)
        df['top']    = df['top'].astype(int)
        df['bottom'] = df['bottom'].astype(int)

        # await asyncio.sleep(1)

        return df
    
    def get_font_size(self, df):
        '''
        Function to calculate font size based on bounding box dimensions.

        Inputs:
            - df (pd.DataFrame): DataFrame containing bounding box information.

        Output:
            - df (pd.DataFrame): Updated DataFrame with calculated font sizes.
        '''
    
        df['font_size'] = df.bottom - df.top

        # Check if there's more than one row
        if len(df) > 1:
            df['font_size'] = (df['font_size'] - df['font_size'].mean()) / (df['font_size'].std() + 1e-6)
        else:
            # Handle single-row scenario
            df['font_size'] = 0  # Or any other logic you deem fit for single rows

        df['font_size'] = (df['font_size'].apply(lambda x: round(x)) + 10).astype(int)

        return df
 
    def substract_bounding_boxes(self, df, img, erotion_percent = 0):
        '''
        Function to subtract regions within bounding boxes from the image.

        Inputs:
            - df (pd.DataFrame): DataFrame containing bounding box information.
            - img (np.ndarray): Input image.
            - erotion_percent (float): Percentage of erosion for bounding boxes (default: 0).

        Output:
            - img_out (np.ndarray): Image with regions within bounding boxes subtracted.
        '''
    
        img_out = img.copy()
        
        for i, row in df.iterrows():

            width = row['right'] - row['left']
            erotion_width = int(round((width * erotion_percent) / 100))

            height = row['bottom'] - row['top']
            erotion_height = int(round((height * erotion_percent) / 100))


            img_out[ (row['top'] + erotion_height)  : (row['bottom'] - erotion_height), 
                     (row['left'] + erotion_width) : (row['right'] - erotion_width) ] = 0


        return img_out
    
    def close_shape_gaps5(self, image, ocr,
                      dist_threshold_percent = 30, 
                      activation_lower_th = 40, 
                      activation_upper_th = 70):
        '''
        Function to close gaps between shapes in an image.

        Inputs:
            - image (np.ndarray): Input processed image.
            - ocr (pd.DataFrame): DataFrame containing OCR information.
            - dist_threshold_percent (int): Percentage threshold for distance threshold (default: 30).
            - activation_lower_th (int): Lower threshold for activation (default: 40).
            - activation_upper_th (int): Upper threshold for activation (default: 70).

        Output:
            - img_out (np.ndarray): Image with gaps closed.
        '''

        img = image.copy()
        img = (1-img) * 10

        kernel = np.ones((3, 3), np.uint8)
        kernel[1,1] = 10

        dst = cv2.filter2D(img,-1,kernel).astype(int)

        points_thr = np.where((dst > activation_lower_th) & (dst < activation_upper_th))

        points = []
        for p_i in range(len(points_thr[0])): 
            points.append([points_thr[0][p_i], points_thr[1][p_i]])

        points = np.stack(points, axis=0)

        nodes_points = []

        nodes_points.extend([[row.top, row.left] for i, row in ocr.iterrows()])
        nodes_points.extend([[row.top, row.right] for i, row in ocr.iterrows()])
        nodes_points.extend([[row.bottom, row.right] for i, row in ocr.iterrows()])
        nodes_points.extend([[row.bottom, row.left] for i, row in ocr.iterrows()])

        nodes_points   = np.array(nodes_points)
        dist_matrix    = euclidean_distances(points)
        max_bb_height  = (ocr.bottom - ocr.top).max()
        dist_threshold = int((max_bb_height * dist_threshold_percent)/100)

        below_th = np.where((dist_matrix < dist_threshold) & (dist_matrix > 0)) # zero is trivial distance, no need to fill any gap

        img_out = image.copy()

        for i in range(len(below_th[0])):

            p1 = points[below_th[0][i]]
            p2 = points[below_th[1][i]]

            dist_to_nodes = euclidean_distances(np.stack([p1, p2]), nodes_points)
            closest_node = np.argmin(dist_to_nodes) % len(ocr)

            closest_node_height = ocr.loc[closest_node, 'bottom'] - ocr.loc[closest_node, 'top']

            dist_threshold = int((closest_node_height * dist_threshold_percent)/100)

            if np.linalg.norm(p2-p1) < dist_threshold:

                cv2.line(img_out, [p1[1],p1[0]], [p2[1],p2[0]],  (1, 1, 1), thickness=1)
        

        return img_out
    
    def stamp_bounding_boxes_on_image(self, df, img, erotion_percent = 10):
        '''
          Function to stamp bounding boxes on an image.

          Inputs:
              - df (pd.DataFrame): DataFrame containing bounding box information.
              - img (np.ndarray): Input image.
              - erotion_percent (int): Percentage of erosion for bounding boxes (default: 10).

          Output:
              - img_out (np.ndarray): Image with bounding boxes stamped.
        '''
    
        img_out = img.copy()
        for i, row in df.iterrows():
            
            width = row['right'] - row['left']
            erotion_width = int(round((width * erotion_percent) / 100))

            height = row['bottom'] - row['top']
            erotion_height = int(round((height * erotion_percent) / 100))


            img_out[ (row['top'] + erotion_height)  : (row['bottom'] - erotion_height), 
                     (row['left'] + erotion_width) : (row['right'] - erotion_width) ] = 1

        return img_out
    
    def get_filled_shapes(self,img):
        '''
        Function to extract filled shapes from an image.

        Inputs:
            - img (np.ndarray): Input processed image.

        Output:
            - img_out (np.ndarray): Image with filled shapes.
        '''
    
        contours, tree = cv2.findContours(cv2.convertScaleAbs(img), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        img_out = np.zeros_like(img)

        for i, contour in enumerate(contours):
            cv2.drawContours(img_out, [contour], 0, (1, 1, 1), thickness=cv2.FILLED)

        return img_out
    
    def get_masks(self,img, max_iter=10):
        '''
        Function to obtain masks for nodes and edges.

        Inputs:
            - img (np.ndarray): Input image.
            - max_iter (int): Maximum number of iterations (default: 10).

        Outputs:
            - nodes_mask (np.ndarray): Mask for nodes.
            - edges_mask (np.ndarray): Mask for edges.
        '''
    

        kernel = np.ones((3, 3), np.uint8)

        img_eroded = [img.copy()]
        contours_iter = []

        for i in range(max_iter):
            contours, tree = cv2.findContours(cv2.convertScaleAbs(img_eroded[-1]), 
                                              cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours_iter.append(contours)
            img_eroded.append(cv2.erode(img_eroded[-1], kernel, iterations = 1))

        min_contours = len(contours_iter[-1])
        min_contours_iteration = len(contours_iter)-1

        for i in range(len(contours_iter)-1, -1, -1):
            if len(contours_iter[i]) > min_contours:
                min_contours_iteration = i+1
                break


        nodes_mask = img_eroded[min_contours_iteration]

        nodes_mask_dilated = cv2.dilate(nodes_mask, kernel, iterations=min_contours_iteration+1)
        edges_mask = np.maximum((img_eroded[0] - nodes_mask_dilated), 0)


        return nodes_mask, edges_mask
    
    ########################## Edges Direction Processing ###########################


    def preprocess_for_arrow_detection(self,img_gray,dilate,erode):
     
        img_blur = cv2.GaussianBlur(img_gray, (5, 5), 1)

        img_canny = cv2.Canny(img_blur, 50, 50)

        kernel = np.ones((3, 3))

        img_dilate = cv2.dilate(img_canny, kernel, iterations=dilate)
        img_erode  = cv2.erode(img_dilate, kernel, iterations=erode)

        return img_erode
    
    def find_tip(self, points, convex_hull):
    
        length = len(points)

        indices = np.setdiff1d(range(length), convex_hull)

        for i in range(2):

            j = indices[i] + 2
            if j > length - 1:
                j = length - j

            if np.all(points[j] == points[indices[i - 1] - 2]):
                return tuple(points[j])

    def find_arrow_tail(self, arrow_tip, contour):
        # Calculate the distances between the arrow tip and all points in the contour
        distances = [np.linalg.norm(arrow_tip - point[0]) for point in contour]

        # Find the index of the point with the maximum distance (farthest point)
        farthest_point_index = np.argmax(distances)

        # Get the farthest point coordinates
        arrow_tail = tuple(contour[farthest_point_index][0])

        return arrow_tail
    def detect_arrows(self, img, dilate_max=5, erode_max=5, rounding_max = 0.05, rounding_step=0.002):
    
        arrow_contours = []

        arrow_tips = []
        arrow_origins = []

        dilates = list(range(0, dilate_max))
        erotions = list(range(0, erode_max))
        roundings = np.arange(0.001, rounding_max, rounding_step)

        combinations = []

        for d in dilates:
            for e in erotions:
                for r in roundings:
                    combinations.append({'dilate': d, 'erotion': e, 'rounding': r})

        for comb in combinations:

            contours, hierarchy = cv2.findContours(self.preprocess_for_arrow_detection(img, comb['dilate'], comb['erotion']), 
                                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

            for cnt in contours:
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, comb['rounding'] * peri, True)
                hull = cv2.convexHull(approx, returnPoints=False)
                sides = len(hull)

                if 6 > sides > 3 and sides + 2 == len(approx):

                    bol_repeated_contour = False

                    for i,c in enumerate(arrow_contours):
                        if cv2.matchShapes(c, cnt, 1, 0.0) < 1:
                            bol_repeated_contour = True
                            break

                    if bol_repeated_contour == False:
                        arrow_contours.append(cnt)
                        arrow_tip = self.find_tip(approx[:, 0, :], hull.squeeze())

                        if arrow_tip:
                            arrow_tips.append(arrow_tip)
                            ### one way to caclulate arrow length
                            ### leave here for comparision of calculations
                            # arrow_tail = self.find_arrow_tail(arrow_tip, cnt)
                            # caculate the lenth
                            # length = np.linalg.norm(np.array(arrow_tip) - np.array(arrow_tail))
                            # arrow_lengths.append(length)
                            dist_mat = euclidean_distances(np.expand_dims(arrow_tip, axis=0), np.squeeze(cnt))
 
                            arrow_origin = np.squeeze(cnt)[np.argmax(dist_mat)]
                            arrow_origins.append(arrow_origin)


        arrow_origins = np.array(arrow_origins)
        arrow_tips    = np.array(arrow_tips)

        return arrow_origins, arrow_tips
    
    def get_edges_endpoints_directionality(self,edges_endpoints, tips, origins, dist_threshold=50):

        tips_origins = np.concatenate([tips, origins], axis=1)
        origins_tips = np.concatenate([origins, tips], axis=1)
        # edges_endpoints = np.array(edges_endpoints)
        dist_mat_tips_origins = euclidean_distances(edges_endpoints.reshape((edges_endpoints.shape[0], 4)), tips_origins)
        dist_mat_origins_tips = euclidean_distances(edges_endpoints.reshape((edges_endpoints.shape[0], 4)), origins_tips)

        min_dist = []
        min_dist.append(np.min(dist_mat_tips_origins, axis=1))
        min_dist.append(np.min(dist_mat_origins_tips, axis=1))

        origins_or_tips = np.argmin(min_dist, axis = 0)

        abs_min_dist = np.array([min_dist[selected][i] for i, selected in enumerate(origins_or_tips)])

        directions = [None] * len(edges_endpoints)

        for index in np.where(abs_min_dist < dist_threshold)[0]:
            directions[index] = origins_or_tips[index]

        return directions

    def get_conections(self, nodes_df, edges_endpoints, edges_directionalities, img, dist_threshold_percentage=5):

        nodes_contours = []
        nodes_ids = []
        edge_id = 0
        edges_id = []
        for i, row in nodes_df.iterrows():
            img_out = np.zeros_like(img, dtype=np.uint16)

            img_out[row.top: row.bottom, row.left: row.right] = 1

            contour, tree = cv2.findContours(cv2.convertScaleAbs(img_out), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            assert len(contour) == 1

            nodes_contours.append(contour[0])
            nodes_ids.append(row.node_id)

        edges_endpoints = edges_endpoints.astype(np.uint16)

        connections = []
        destination_nodes = []

        dist_threshold_in_pixels = int((dist_threshold_percentage / 100) * img.shape[0])

        for edge_i, edge in enumerate(edges_endpoints):

            connection = [None, None]

            for i_endpoint, endpoint in enumerate(edge):

                min_dist_to_node = 9e3
                min_dist_node_n = -1

                for i_node, node in enumerate(nodes_contours):

                    min_dist = cv2.pointPolygonTest(node, endpoint, True) * (-1)

                    if min_dist < min_dist_to_node:
                        min_dist_to_node = min_dist
                        min_dist_node_n = nodes_ids[i_node]

                if min_dist_to_node < dist_threshold_in_pixels:
                    connection[i_endpoint] = min_dist_node_n

            if connection[0] is not None and connection[1] is not None and connection[0] != connection[1]:
                connections.append(connection)
                edges_id.append(edge_id)
                if edges_directionalities[edge_i] is not None:
                    dest_node = connection[edges_directionalities[edge_i]]
                else:
                    dest_node = None

                destination_nodes.append(dest_node)
            edge_id = edge_id + 1

        df_pre = pd.DataFrame(connections, columns=['node a', 'node b'])
        df_pre.insert(column='destination node', loc=2, value=destination_nodes)

        return df_pre, edges_id

    ########################## Edges Direction Processing ###########################

    def get_edges_endpoints(self, edges_mask, min_edge_length_percentage=3):

        final_edges = []

        contour_idswithendpoint = []
        edge_lengths = []

        edge_thickness = []
        
        min_edge_length_pixels = (min_edge_length_percentage / 100) * edges_mask.shape[0]
        
        contours, tree = cv2.findContours(cv2.convertScaleAbs(edges_mask), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contour_data = []  # A list to store (contour_id, contour, endpoints) tuples
        contour_id = 0

        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            edge_lengths.append(perimeter)
            contours_length = len(contour)

            # Avoid division by zero
            if contours_length == 0:
                contours_length = 1
            area = cv2.contourArea(contour)
            # Calculate the thickness of the contour
            thickness = area / contours_length
            edge_thickness.append(thickness)

            c = max([contour], key=cv2.contourArea)

            extreme_points = []

            extreme_points.append(np.array(c[c[:, :, 0].argmin()][0]))
            extreme_points.append(np.array(c[c[:, :, 0].argmax()][0]))
            extreme_points.append(np.array(c[c[:, :, 1].argmin()][0]))
            extreme_points.append(np.array(c[c[:, :, 1].argmax()][0]))

            extreme_points = np.stack(extreme_points, axis=0)

            contour_data.append((contour_id, contour, extreme_points))

            dist_mat = euclidean_distances(extreme_points)
        
            if np.max(dist_mat) > min_edge_length_pixels:
                ext_indeces = np.unravel_index(np.argmax(dist_mat), shape=dist_mat.shape)

                final_endpoints = [extreme_points[ext_indeces[0]], extreme_points[ext_indeces[1]]]

                final_edges.append(final_endpoints)
                # Step 2 (Continued): Record contour ID of the endpoints

                contour_idswithendpoint.append(contour_id)
            contour_id = contour_id + 1

        n = len(edge_lengths)
        ids = np.arange(n).reshape((-1, 1))
        combined_table = np.column_stack((ids, edge_lengths, edge_thickness))

        selected_rows = combined_table[np.isin(combined_table[:, 0], contour_idswithendpoint)]
        
        return np.stack(final_edges), selected_rows

    def get_nodes(self, ocr, nodes_mask, threshold_iou=0.8):
        """
        Identifies nodes in an image based on OCR results and a mask of node contours. Nodes are determined by 
        calculating the Intersection over Union (IoU) of OCR bounding boxes and node contours, and those with IoU 
        exceeding a specified threshold are considered part of a node.
        
        Parameters:
        - ocr (DataFrame): A pandas DataFrame containing OCR results with bounding box coordinates.
        - nodes_mask (ndarray): A binary mask of node contours.
        - threshold_iou (float): The IoU threshold to determine if an OCR result belongs to a node.
        
        Returns:
        - DataFrame: A pandas DataFrame containing aggregated information for each identified node, including combined text,
                    bounding box coordinates, and font size. Returns an empty DataFrame if no nodes meet the criteria.
        """

        df = ocr.copy()
        df['node_id'] = np.nan
        nodes_contours, tree = cv2.findContours(cv2.convertScaleAbs(nodes_mask), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for i, row in df.iterrows():

            area = (row['right'] - row['left']) * (row['bottom'] - row['top'])

            max_iou = 0
            max_iou_i_node = -1

            for i_node, contour in enumerate(nodes_contours):

                empty_img = np.zeros_like(nodes_mask)

                cv2.drawContours(empty_img, [contour], 0, (1, 1, 1), thickness=-1)

                intersection = empty_img[row['top']:row['bottom'], row['left']:row['right']].sum()

                iou = intersection / area

                if iou > max_iou:
                    max_iou = iou
                    max_iou_i_node = i_node

            if max_iou > threshold_iou:
                df.at[i, 'node_id'] = max_iou_i_node
            
        if df['node_id'].notna().any():
        
            df = df[df['node_id'].notna()]
            df['node_id'] = df['node_id'].astype(int)
            # df['text'] = df.groupby('node_id')['text'].transform(lambda x: '\n'.join(x))
            df = df.groupby('node_id').agg({
                'left': 'min',
                'right': 'max',
                'top': 'min',
                'bottom': 'max',
                'font_size': 'max',
                'text': lambda x: '\n'.join(map(str, x))
            }).reset_index()


            df.drop_duplicates('text', inplace=True)

            df = df[df.node_id.notna()]
            df.node_id = df.node_id.astype(int)

            df.reset_index(drop=True, inplace=True)

            return df
        else:

            return pd.DataFrame()
        
    def join_close_nodes(self,
                         ocr,
                         vertical_distance_threshold_percent=25,
                         horizontal_distance_threshold_percent=50):

        df = ocr.copy()

        while True:

            flag_updates_made = False

            for i,row_a in df.iterrows():
                for j,row_b in df.iterrows():

                    row_a_height = row_a.bottom - row_a.top
                    row_b_height = row_b.bottom - row_b.top

                    row_a_width = row_a.right - row_a.left
                    row_b_width = row_b.right - row_b.left

                    mean_height = (row_a_height + row_b_height) / 2
                    mean_width  = (row_a_width + row_b_width) / 2

                    vertical_distance_threshold_pixels   = (vertical_distance_threshold_percent / 100) * mean_height
                    horizontal_distance_threshold_pixels = (horizontal_distance_threshold_percent / 100) * mean_width

                    if (j > i and 
                        abs(row_b.top - row_a.bottom) < vertical_distance_threshold_pixels and
                        abs(row_b.left - row_a.left) < horizontal_distance_threshold_pixels):

                        df.at[i, 'text'] = row_a.text + ' ' + row_b.text
                        df.at[i, 'bottom'] = row_b.bottom
                        df.at[i, 'left'] = min(row_a.left, row_b.left)
                        df.at[i, 'right'] = max(row_a.right, row_b.right)
                        df.at[i, 'font_size'] = row_a.font_size#(row_a.font_size + row_b.font_size) / 2

                        df = df.drop(j, axis=0)
                        df.reset_index(drop=True, inplace=True)

                        flag_updates_made = True

                        break

                if flag_updates_made:
                    break

            if flag_updates_made == False:
                break

        return df
    

    def spellcheck2(self, text):
        text = text.replace('&', 'and')
        output = TextBlob(text)
        output = str(output.correct())
        output = output.replace(' and ', ' & ')
        return output
    
    def compute_iou(self, box1, box2):
        x1, y1, x2, y2 = box1
        x1_, y1_, x2_, y2_ = box2

        # Calculate intersection rectangle coordinates
        xA = max(x1, x1_)
        yA = max(y1, y1_)
        xB = min(x2, x2_)
        yB = min(y2, y2_)

        # Calculate the area of intersection
        inter_area = max(0, xB - xA + 1) * max(0, yB - yA + 1)

        # Calculate the area of each box
        box1_area = (x2 - x1 + 1) * (y2 - y1 + 1)
        box2_area = (x2_ - x1_ + 1) * (y2_ - y1_ + 1)

        # Calculate the area of union
        union_area = box1_area + box2_area - inter_area

        # Calculate IoU
        iou = inter_area / union_area

        return iou

    def extract_feature(self,file_prefix,image_file,bucket_name):
        '''
        Function to extract features from the OCR data and image.

        Inputs:
            - file_prefix (str): image file perfix without format.
            - image_file (str): Path to the image file.
            - bucket_name (str): Name of storage bucket.

        Outputs:
            - nodes_df (pd.DataFrame): DataFrame containing node information.
            - connections_df (pd.DataFrame): DataFrame containing connection information.
            - message (str): System message to handle the errors.
        '''
        logger.info('Step 1: Read image from bucket')
        ############################## initialize some settings ################################
        ## initialize a message wil be saved to fire store to keep the status of the processing.
        initial_message = ''
        ## setting a groupd of iou thresholds for detecting and matching final possible nodes using
        ## the method get_nodes()
        iou_thresholds = [0.1, 0.05]
        ## initialize an empty nodes df and connections_df
        nodes_df = pd.DataFrame()
        connections_df = pd.DataFrame()
        client = storage.Client()
        #########################################################################################
    
        # Get the GCS bucket and blob
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(image_file)

        # Download the image data
        image_data = blob.download_as_string()
        # Create a BytesIO object to work with the bytes data
        bytes_io = io.BytesIO(image_data)
        image_open = Image.open(bytes_io)
        if image_open.mode == 'RGBA':
            image_open = image_open.convert('RGB') ### jpegimage object
        
        # convert to array
        image_np = np.array(image_open)
      
        logger.info('Step 2: Start to OCR')
        try:
            self.aws_textract(file_prefix,image_file)
        except Exception as e:
            logger.error(e)
            initial_message = "Failed to do OCR due to the unsupported format of uploaded mind map."
            return nodes_df, connections_df, initial_message
        
        ocr = self.get_ocr_data(file_prefix)
        imagetest = []
        imagetest.append(image_np)
        try:
            df_ocr_test = self.set_bounding_boxes_in_pixels(ocr, imagetest[-1])
        except Exception as e:
            logger.error(e)
            initial_message = 'Bad performance detection by OCR, stop processing'
            return nodes_df,connections_df,initial_message
        df_ocr_test = self.get_font_size(df_ocr_test)
        
        df_ocr_test = self.join_close_nodes(df_ocr_test, vertical_distance_threshold_percent=25, horizontal_distance_threshold_percent=50)
        df_ocr_test['Location'] = df_ocr_test.apply(lambda row: [row['left'], row['top'], row['right'], row['bottom']], axis=1)
        df_ocr_test = df_ocr_test[['text', 'font_size','Location']]
        

        df_ocr_test_final = df_ocr_test
        
        df_ocr_test_final['left'] = df_ocr_test_final['Location'].apply(lambda x: x[0])
        df_ocr_test_final['top'] = df_ocr_test_final['Location'].apply(lambda x: x[1])
        df_ocr_test_final['right'] = df_ocr_test_final['Location'].apply(lambda x: x[2])
        df_ocr_test_final['bottom'] = df_ocr_test_final['Location'].apply(lambda x: x[3])


        logger.info('Step 3: Start to use drawing model to predict.')
  
        drawing_df_test = self.get_drawings_predictions(image_open, 0.7)
        
        
        threshold = 0.3
        final_matched_rows = []
        ####### check the drawing_df_test empty or not 
        if drawing_df_test.empty:
            final_nodes_df = df_ocr_test_final
        else:
            for i, row in drawing_df_test.iterrows():
                for _, row_ocr in df_ocr_test_final.iterrows():
                    iou = self.compute_iou(row['Location'], row_ocr['Location'])
                    if iou >= threshold:
                        final_matched_rows.append(i)
                        break
            unmatched_df = drawing_df_test.loc[~drawing_df_test.index.isin(final_matched_rows)].reset_index(drop=True)
            
            if 'Location' in unmatched_df.columns:
                unmatched_df = unmatched_df[['Location']]
                unmatched_df.columns = ['Location']
                unmatched_df['text'] = ['drawing_0' + str(i) for i in range(unmatched_df.shape[0])]

                unmatched_df['left'] = unmatched_df['Location'].apply(lambda x: int(x[0]))
                unmatched_df['top'] =  unmatched_df['Location'].apply(lambda x: int(x[1]))
                unmatched_df['right'] = unmatched_df['Location'].apply(lambda x: int(x[2]))
                unmatched_df['bottom'] = unmatched_df['Location'].apply(lambda x: int(x[3]))
                
                unmatched_df = self.get_font_size(unmatched_df)
                
            final_nodes_df = pd.concat([df_ocr_test_final, unmatched_df[['text', 'font_size','Location','left','top','right','bottom']]], ignore_index=True)
            
            df_ocr_test_final = final_nodes_df.drop(columns=['Location'])

        
        logger.info('Step 4: Start to use edges model to predict.')

        image_final_test = []
        read_image = self.open_image(image_file,bucket_name)
        image_final_test.append(read_image)

        df_ocr_test_final = self.join_close_nodes(df_ocr_test_final, 
            vertical_distance_threshold_percent=25, 
            horizontal_distance_threshold_percent=50)
        image_final_test.append(self.stamp_bounding_boxes_on_image(df_ocr_test_final, 
                                                                   image_final_test[-1], 
                                                                   erotion_percent = 10))  ################ 20 % errotion too high ############################

        image_no_thresholding = cv2.convertScaleAbs(self.substract_bounding_boxes(df_ocr_test_final, read_image, 20))
        
        arrow_origins, arrow_tips = self.detect_arrows(img=image_no_thresholding, 
                                                       dilate_max=5, 
                                                       erode_max=5, 
                                                       rounding_max = 0.05, 
                                                       rounding_step=0.002)
        image_final_test.append(self.threshold_image(image_final_test[-1]))

        image_final_test.append(self.get_filled_shapes(image_final_test[-1]))################# need to fill the shapes before calculating the nodes masks!!! ####################################################

        logger.info('Step 5: Start to compute nodes and edges masks.')
        nodes_mask, edges_mask = self.get_masks(image_final_test[-1], max_iter=5) #### 4 or 5
        image_final_test.append(nodes_mask)
        image_final_test.append(edges_mask)
        
        edges_endpoints,edges_endpoints_features = self.get_edges_endpoints(edges_mask, min_edge_length_percentage=0.03)#1.5

        edges_directionalities = self.get_edges_endpoints_directionality(edges_endpoints, 
                                                                         arrow_tips, 
                                                                         arrow_origins, 
                                                                         dist_threshold=50)
        
        #uses vit to predict edge_tip and compares both opencv and vit approaches using a simple logic
        final_edges_directionalities = self.get_edges_endpoints_directionality_vit(edges_endpoints, 
                                                                                   image_final_test[0], 
                                                                                   edges_directionalities,
                                                                                   score_threshold=0.3)
        for threshold_iou in iou_thresholds:
            nodes_df = self.get_nodes(df_ocr_test_final, nodes_mask, threshold_iou = 0.1) ### 0.1 to 0.3
            # check if nodes are detected
            if not nodes_df.empty:
                break
            else:
                logger.info(f"No nodes detected with IOU threshold {threshold_iou}. Retrying with a lower threshold...")
        if nodes_df.empty:
            logger.info("Nodes could not be detected. The uploaded mind map may contain excessive noise or be of low quality. Please attempt the process with a different mind map.")
            initial_message = "Nodes could not be detected. The uploaded mind map may contain excessive noise or be of low quality. Please attempt the process with a different mind map."
            connections_df = pd.DataFrame()
            return nodes_df, connections_df, initial_message
        
        nodes_df['text'] = nodes_df.text.apply(self.spellcheck2)
        nodes_df = nodes_addcolor(nodes_df, read_image,bucket_name)
        connections_df,edges_id = self.get_conections(nodes_df, 
                                                      edges_endpoints, 
                                                      final_edges_directionalities, 
                                                      image_final_test[-1], 
                                                      dist_threshold_percentage = 20)


        final_edges_feature = edges_endpoints_features[edges_id]
        df_edge_features = pd.DataFrame(final_edges_feature, columns=['id', 'length', 'thickness'])

        connections_df = pd.concat([connections_df, df_edge_features], axis=1)

        connections_df = self.remove_repeated_connections(connections_df)
        
        ### determine node level
    
        detect_instance = DetermineNodesHierarchy(nodes_df,
                                                  connections_df,
                                                  bucket_name,
                                                  image_file,
                                                  OPENAI_API_KEY
                                                  )
        nodes_hierarchy= detect_instance.process()
        final_nodes_df= nodes_df.copy()
        # Update node_level column in new_nodes_df based on hierarchy dictionary
        final_nodes_df['node_level'] = final_nodes_df['node_id'].map(nodes_hierarchy)
        initial_message = "Successfully processed."
        return final_nodes_df, connections_df, initial_message

    def generate_json_output(self,
                             nodes_df,
                             connections_df,
                             image_file,
                             user_id,
                             message
                             ):

        '''
        Function to generate the JSON output file.

        Inputs:
            - nodes_df (pd.DataFrame): DataFrame containing node information.
            - connections_df (pd.DataFrame): DataFrame containing connection information.
            - image_file (str): Path to the image file.

        Output:
            - graph (dict): Graph dictionary containing nodes, edges, and image information.
        '''
        # Create nodes dictionary
        image_id = str(uuid.uuid4())
        nodes = []
        if not nodes_df.empty:
            for index, row in nodes_df.iterrows():
                node_id = row['node_id'] 
                attributes = {
                    'position':{'x': (row['left'] + row['right']) / 2,  
                    'y': (row['top'] + row['bottom']) / 2},

                    'color': row['color'],
                    'font_size': row['font_size'],
                    'text': row['text'],
                    'node_level': row['node_level']
                } 
                node = {
                    'node_id': node_id,
                    'attributes': attributes
                } 
                nodes.append(node)

        # Create edges list
        edges = []
        if not connections_df.empty:
            for index, row in connections_df.iterrows():
                edge = {
                    'node a': int(row['node a']),
                    'node b': int(row['node b']),
                  }
                if pd.isna(row['destination node']):
                    destination_node = 'None'
                else:
                    destination_node = int(row['destination node'])

                edge_info={
                    'edge':edge,
                    'destination_node':destination_node,
                    'thickness': float(row['thickness']),
                    'length': float(row['length'])
                } 
                edges.append(edge_info)

        # Create graph dictionary
        graph = {'image_id':image_id,
                 'user_id': user_id,
                 'image_name':image_file,
                 'graph':{'nodes': nodes,
                        'edges': edges
                    },
                 'message':message
                }
        
        return graph

# #########################  Load detectors (ViT) models ###########################



    def get_drawings_predictions(self, image, threshold=0.7):


        inputs = self.drawing_image_processor(images=image, return_tensors="pt")
        
        outputs = self.drawing_model(**inputs)
        
        target_sizes = torch.tensor([image.size[::-1]])
        
        results = self.drawing_image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=threshold)[0]
        

        # List to collect detection details
        detections = []
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            box = [round(i, 2) for i in box.tolist()]
            detection_info = {
                'Label': self.drawing_model.config.id2label[label.item()],
                'Confidence Score': round(score.item(), 3),
                'Location': box
            }
            detections.append(detection_info)

            # draw.rectangle(box, outline="red", width=1)


        # Convert the list of dictionaries to a DataFrame and save as a CSV file
        detections_df = pd.DataFrame(detections)

        return detections_df

    def get_edge_tip_predictions(self, image, threshold=0.1):

        img = Image.fromarray(image)
        inputs = self.edge_tip_image_processor(images=img, return_tensors="pt")
        outputs = self.edge_tip_model(**inputs)

        target_sizes = torch.tensor([img.size[::-1]])
        return \
        self.edge_tip_image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=threshold)[
            0]

    def get_node_predictions(self, image, threshold=0.7):


        inputs = self.node_image_processor(images=image, return_tensors="pt")
        outputs = self.node_model(**inputs)

        target_sizes = torch.tensor([image.size[::-1]])
        results = self.node_image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=threshold)[0]

        # List to collect detection details
        detections = []
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            box = [round(i, 2) for i in box.tolist()]
            detection_info = {
                'Label': self.node_model.config.id2label[label.item()],
                'Confidence Score': round(score.item(), 3),
                'Location': box
            }
            detections.append(detection_info)


        # Convert the list of dictionaries to a DataFrame and save as a CSV file
        detections_df = pd.DataFrame(detections)

        return detections_df

    def get_edges_endpoints_directionality_vit(self, edges_endpoints, image, edges_directionalities, score_threshold):

        edge_tips_vit = self.get_edge_tip_predictions(image)

        tolerance_margin_pixels = 5
        min_score = 0.3
        min_difference_score = 0.1

        edges_directionalities_vit = []
        vit_scores = []

        for i, edge_endpoint in enumerate(edges_endpoints):

            x_0 = edge_endpoint[0][0]
            y_0 = edge_endpoint[0][1]

            x_1 = edge_endpoint[1][0]
            y_1 = edge_endpoint[1][1]

            scores_0 = [0]
            scores_1 = [0]

            for j, edge_tip_vit in enumerate(edge_tips_vit['boxes']):

                bb_x0 = edge_tip_vit[0] - tolerance_margin_pixels
                bb_x1 = edge_tip_vit[2] + tolerance_margin_pixels

                bb_y0 = edge_tip_vit[1] - tolerance_margin_pixels
                bb_y1 = edge_tip_vit[3] + tolerance_margin_pixels

                if (x_0 >= bb_x0 and x_0 <= bb_x1 and
                        y_0 >= bb_y0 and y_0 <= bb_y1):
                    scores_0.append(round(float(edge_tips_vit['scores'][j]), 2))

                if (x_1 >= bb_x0 and x_1 <= bb_x1 and
                        y_1 >= bb_y0 and y_1 <= bb_y1):
                    scores_1.append(round(float(edge_tips_vit['scores'][j]), 2))

            max_score_0 = np.max(scores_0)
            max_score_1 = np.max(scores_1)

            if max_score_0 > min_score and max_score_0 > max_score_1 + min_difference_score:
                edges_directionalities_vit.append(0)
                vit_scores.append(max_score_0)

            elif max_score_1 > min_score and max_score_1 > max_score_0 + min_difference_score:
                edges_directionalities_vit.append(1)
                vit_scores.append(max_score_1)

            else:
                edges_directionalities_vit.append(None)
                vit_scores.append(0)

        # compare vit and opencv approaches

        final_edges_directionalities = []

        for i in range(len(edges_directionalities)):

            if edges_directionalities[i] == edges_directionalities_vit[i]:

                final_edges_directionalities.append(edges_directionalities[i])



            elif edges_directionalities[i] == None and vit_scores[i] > score_threshold:

                final_edges_directionalities.append(edges_directionalities_vit[i])



            elif edges_directionalities_vit[i] == None:

                final_edges_directionalities.append(edges_directionalities[i])


            else:

                if vit_scores[i] > score_threshold:
                    final_edges_directionalities.append(edges_directionalities_vit[i])
                else:
                    final_edges_directionalities.append(edges_directionalities[i])

        return final_edges_directionalities

    def remove_repeated_connections(self, df):

        to_remove = []

        for i, row in df.iterrows():

            repeated_rows = df[(((df['node a'] == row['node a']) & (df['node b'] == row['node b'])) |
                                ((df['node a'] == row['node b']) & (df['node b'] == row['node a'])))]

            if len(repeated_rows) > 1:

                flag_done = False

                for j, row2 in repeated_rows.iterrows():

                    if np.isnan(row2['destination node']) == False:
                        to_remove.extend(repeated_rows.index)
                        to_remove.remove(j)
                        flag_done = True
                        break

                if flag_done == False:
                    to_remove.extend(repeated_rows.index[1:])

        df.drop(index=list(set(to_remove)), inplace=True)

        return df
