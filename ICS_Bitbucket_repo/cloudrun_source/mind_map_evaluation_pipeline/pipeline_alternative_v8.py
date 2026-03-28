from ultralytics import YOLO
import pandas as pd
import numpy as np
from PIL import Image
import boto3
import io
from gcp import *
from google.cloud import storage
import uuid
from determineNodeHierarchy import DetermineNodesHierarchy
from detect_colour import *

import time
logger = gcp_logger()
run_conf = gcp_get_config()
PROJECT = gcp_project_id()
func_conf = gcp_get_config()
project_number = gcp_project_number(PROJECT)
OPENAI_API_KEY = gcp_get_secret(project_number,func_conf.get('openai_api_key', 'openai_api_key_name' ))

AWS_ACCESS_KEY_ID = gcp_get_secret(project_number,func_conf.get('aws_access_key_id', 'aws_access_key_name' ))
AWS_SECRET_ACCESS_KEY = gcp_get_secret(project_number,func_conf.get('aws_secret_access_key', 'aws_secret_access_key_name' ))

### the following two lines would load the YOLO V9 model would be loading in the app.py in flask startup
# model_name= 'yolov9_tail.pt'
# model = YOLO(model_name)
class GraphFeatureExtractionPipeline:
    def __init__(self,
                 image_file_path: str,
                 model,
                 predict_from_local:bool = False,
                 model_thresholds: dict = {0: 0.3, 1: 0.1, 2: 0.1, 3: 0.4}
                ):
        """
        Initialize the GraphFeatureExtractionPipeline class.

        Args:
            image_file_path (str): The path to the image file.
            model: The YOLO model instance.
            predict_from_local (bool): Flag indicating if the image should be loaded from a local path.
            model_thresholds (dict): Dictionary specifying the confidence thresholds for different classes.
        """
        self.image_file_path = image_file_path
        self.image_data = None
        self.model = model
        self.predict_from_local =predict_from_local
        self.model_thresholds = model_thresholds
        self.client = storage.Client()
        self.textract_client = boto3.client('textract',
                        aws_access_key_id=AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                        region_name="us-east-1"
                    )
    def read_image_data(self):
        """
        Read image data from either a local path or Google Cloud Storage.

        If the image is located in a GCS bucket, it reads the image directly from the bucket.

        Returns:
            Image: The image data as a PIL Image object.
        """
        if self.predict_from_local:
            self.image_data = Image.open(self.image_file_path)
        else:
            bucket_name = self.image_file_path.split("gs://")[-1].split("/")[0]
            blob_name = "/".join(self.image_file_path.split("gs://")[-1].split("/")[1:])
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            try:
                image_data = blob.download_as_bytes()
                self.image_data = Image.open(io.BytesIO(image_data))
                logger.info(f"Successfully read image file {blob_name} from bucket {bucket_name}")
            except Exception as e:
                logger.info(f"Failed to read image file from bucket: {e}")
                raise
        return self.image_data
            
    def format_predicted_results_from_yolo(self, predictions):
        """
        Format the predicted results from the YOLO model into a DataFrame.

        Args:
            predictions (list): The predictions from the YOLO model.

        Returns:
            pd.DataFrame: A DataFrame with columns ['class', 'confidence', 'xmin', 'ymin', 'xmax', 'ymax'] containing the formatted prediction results.
        """
        # Assuming predictions[0].boxes contains the required data
        boxes = predictions[0].boxes
        class_ids = boxes.cls.numpy()
        confidences = boxes.conf.numpy()
        coordinates = boxes.xyxy.numpy().astype(int)  # Ensure coordinates are integers

        formatted_results = []
        for class_id, confidence, (x1, y1, x2, y2) in zip(class_ids, confidences, coordinates):
            formatted_results.append([class_id, confidence, x1, y1, x2, y2])
        
        predictions_df = pd.DataFrame(formatted_results, columns=['class', 'confidence', 'xmin', 'ymin', 'xmax', 'ymax'])
        predictions_df.reset_index(drop=True, inplace=True)
        return predictions_df

    def predict_and_filter_detections(self):
        """
        Predict and filter detections using the YOLO model.

        This method loads the image, makes predictions using the YOLO model, and filters the predictions
        based on the confidence thresholds specified in `self.model_thresholds`.

        Returns:
            pd.DataFrame: A DataFrame with the filtered prediction results.
        """
        self.image_data = self.read_image_data()
        predictions = self.model.predict(self.image_data, 
                                         classes=[0, 1, 2, 3],  # label class edges, edge_tails, edge_tips, nodes
                                         save_txt=False,
                                         show_labels=False,
                                         save=False,
                                         save_conf=False,
                                         conf=0.1  # minimum confidence threshold for a prediction
                                         )
        predictions_df = self.format_predicted_results_from_yolo(predictions)
        filtered_predictions_df = predictions_df[predictions_df.apply(lambda row: row['confidence'] >= self.model_thresholds.get(row['class'], 0), axis=1)]
        return filtered_predictions_df
    
    def calculate_iou(self, box1, box2):
        """
        Calculate the Intersection over Union (IoU) of two bounding boxes.

        IoU is a measure of the overlap between two bounding boxes. This method calculates the IoU
        by finding the intersection area and dividing it by the union area of the two boxes.

        Args:
            box1 (list): The first bounding box [xmin, ymin, xmax, ymax].
            box2 (list): The second bounding box [xmin, ymin, xmax, ymax].

        Returns:
            float: The IoU of the two bounding boxes.
        """
        xA = max(box1[0], box2[0])
        yA = max(box1[1], box2[1])
        xB = min(box1[2], box2[2])
        yB = min(box1[3], box2[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)

        box1Area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2Area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        iou = interArea / float(box1Area + box2Area - interArea)

        return iou
    def calculate_containment(self,box1, box2):
        """
        Calculate the containment of one bounding box within another.

        This method calculates the containment ratio of box2 within box1 by finding the intersection area
        and dividing it by the area of box2.

        Args:
            box1 (list): The first bounding box [xmin, ymin, xmax, ymax].
            box2 (list): The second bounding box [xmin, ymin, xmax, ymax].

        Returns:
            float: The containment ratio of box2 within box1.
        """
        xA = max(box1[0], box2[0])
        yA = max(box1[1], box2[1])
        xB = min(box1[2], box2[2])
        yB = min(box1[3], box2[3])

        interArea = max(0, xB - xA) * max(0, yB - yA)
        box2Area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        containment = interArea / float(box2Area)

        return containment
    
    def merge_boxes(self,boxes):
        """
        Merge multiple bounding boxes into a single bounding box.

        This method takes a list of bounding boxes and returns a single bounding box that encloses all
        the input boxes.

        Args:
            boxes (list): A list of bounding boxes, each defined as [xmin, ymin, xmax, ymax].

        Returns:
            list: A single bounding box [xmin, ymin, xmax, ymax] that encloses all input boxes.
        """
        x_min = min([box[0] for box in boxes])
        y_min = min([box[1] for box in boxes])
        x_max = max([box[2] for box in boxes])
        y_max = max([box[3] for box in boxes])
        return [x_min, y_min, x_max, y_max]
    
    def filter_overlapping_bbx(self,df, iou_threshold=0.8, containment_threshold=0.8):
        """
        Filter overlapping bounding boxes based on IoU and containment thresholds.

        This method filters out overlapping bounding boxes by calculating the IoU and containment ratios.
        If the overlap exceeds the specified thresholds, the boxes are merged.

        Args:
            df (pd.DataFrame): DataFrame containing bounding boxes with columns ['xmin', 'ymin', 'xmax', 'ymax'].
            iou_threshold (float): Threshold for IoU to consider boxes as overlapping.
            containment_threshold (float): Threshold for containment to consider boxes as overlapping.

        Returns:
            pd.DataFrame: A DataFrame with the filtered bounding boxes.
        """
    
        filtered_boxes = []
        indices_to_remove = set()

        for i, row1 in df.iterrows():
            if i in indices_to_remove:
                continue
            box1 = [row1['xmin'], row1['ymin'], row1['xmax'], row1['ymax']]
            overlapping_boxes = [box1]
            for j, row2 in df.iterrows():
                if i != j and j not in indices_to_remove:
                    box2 = [row2['xmin'], row2['ymin'], row2['xmax'], row2['ymax']]
                    iou = self.calculate_iou(box1, box2)
                    containment1 = self.calculate_containment(box1, box2)
                    containment2 = self.calculate_containment(box2, box1)

                    if iou >= iou_threshold or containment1 >= containment_threshold or containment2 >= containment_threshold:
                        overlapping_boxes.append(box2)
                        indices_to_remove.add(j)
            if len(overlapping_boxes) > 1:
                new_box = self.merge_boxes(overlapping_boxes)
                filtered_boxes.append(new_box)
            else:
                filtered_boxes.append(box1)

        filtered_df = pd.DataFrame(filtered_boxes, columns=['xmin', 'ymin', 'xmax', 'ymax'])
        for column in df.columns:
            if column not in ['xmin', 'ymin', 'xmax', 'ymax']:
                filtered_df[column] = df[column].iloc[filtered_df.index].values
        return filtered_df

    def extract_initial_graph_structures_to_df(self, filtered_predictions_df,iou_threshold =0.01):
        """
        Extract initial graph structures (nodes, edges, tips, tails) from filtered predictions.

        This method segregates the filtered predictions into nodes, edges, tips, and tails DataFrames. It also
        assigns unique IDs to nodes and edges and determines whether edges are lines or arrows based on their
        overlap with tips.

        Args:
            filtered_predictions_df (pd.DataFrame): DataFrame with filtered prediction results.
            iou_threshold (float): Threshold for IoU to consider edge and tip overlap.

        Returns:
            tuple: A tuple containing DataFrames for nodes, edges, tips, and tails.
        """
        # Assuming text_data is a DataFrame containing the data172
        initial_nodes_df = filtered_predictions_df[filtered_predictions_df['class'] == 3].reset_index(drop=True)
        initial_edges_df = filtered_predictions_df[filtered_predictions_df['class'] == 0].reset_index(drop=True)
        initial_tips_df = filtered_predictions_df[filtered_predictions_df['class'] == 2].reset_index(drop=True)
        initial_tails_df = filtered_predictions_df[filtered_predictions_df['class'] == 1].reset_index(drop=True)
        # Assign unique IDs and line_or_arrow before filtering
        initial_nodes_df['id'] = ['node_' + str(i) for i in range(len(initial_nodes_df))]

        initial_edges_df['id'] = ['edge_' + str(i) for i in range(len(initial_edges_df))]

        iou_threshold = 0.01
        initial_edges_df['line_or_arrow'] = 'line'  # Default to 'line'
        # Update line_or_arrow based on overlap with tips
        for index, edge in initial_edges_df.iterrows():
            edge_box = [edge['xmin'], edge['ymin'], edge['xmax'], edge['ymax']]
            for _, tip in initial_tips_df.iterrows():
                tip_box = [tip['xmin'], tip['ymin'], tip['xmax'], tip['ymax']]
                iou = self.calculate_iou(edge_box, tip_box)
                if iou > iou_threshold:
                    initial_edges_df.at[index, 'line_or_arrow'] = 'arrow'
                    break
        return initial_nodes_df,initial_edges_df,initial_tips_df,initial_tails_df
    
    def initial_process_detections(self,filtered_predictions_df,iou_threshold=0.8, containment_threshold=0.8):
        """
        Process initial detections to filter overlapping bounding boxes for nodes, edges, tips, and tails.

        This method first extracts the initial graph structures and then filters the overlapping bounding boxes
        for nodes, edges, tips, and tails using the specified IoU and containment thresholds.

        Args:
            filtered_predictions_df (pd.DataFrame): DataFrame with filtered prediction results.
            iou_threshold (float): Threshold for IoU to consider boxes as overlapping.
            containment_threshold (float): Threshold for containment to consider boxes as overlapping.

        Returns:
            tuple: A tuple containing DataFrames for filtered nodes, edges, tips, and tails.
        """
        
        initial_nodes_df,initial_edges_df,initial_tips_df,initial_tails_df = self.extract_initial_graph_structures_to_df(filtered_predictions_df,iou_threshold =0.01)
  

        # Now filter each dataframe
        nodes_df_filtered =self.filter_overlapping_bbx(initial_nodes_df, iou_threshold, containment_threshold)
        edges_df_filtered = self.filter_overlapping_bbx(initial_edges_df[['xmin', 'ymin', 'xmax', 'ymax', 'id', 'line_or_arrow']], iou_threshold, containment_threshold)
        tips_df_filtered = self.filter_overlapping_bbx(initial_tips_df, iou_threshold, containment_threshold)
        tails_df_filtered = self.filter_overlapping_bbx(initial_tails_df, iou_threshold, containment_threshold)

        return nodes_df_filtered, edges_df_filtered, tips_df_filtered, tails_df_filtered
    
    def find_closest_node(self, box, filtered_nodes_df):
        """
        Find the closest node to a given bounding box.

        This method calculates the center of the given bounding box and finds the node with the nearest center
        from the filtered nodes DataFrame.

        Args:
            box (list): The bounding box [xmin, ymin, xmax, ymax].
            filtered_nodes_df (pd.DataFrame): DataFrame containing node information.

        Returns:
            str: The ID of the closest node.
        """
        box_center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        min_distance = float('inf')
        closest_node = None
        for _, node in filtered_nodes_df.iterrows():
            node_center = [(node['xmin'] + node['xmax']) / 2, (node['ymin'] + node['ymax']) / 2]
            distance = ((box_center[0] - node_center[0]) ** 2 + (box_center[1] - node_center[1]) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_node = node['id']
        return closest_node
    
    def assign_closest_nodes_around_tips_and_tails_to_edges(self,
                                                             nodes_df,
                                                             edges_df_with_line_type,
                                                             tips_df,
                                                             tails_df,
                                                             iou_threshold = 0.01):
        """
        Assign the closest nodes around edge tips and edge tails to the edges.

        This method determines which nodes are closest to the tips and tails of edges and assigns these nodes
        to the edges. It updates the edge DataFrame with the IDs of these nodes.

        Args:
            nodes_df (pd.DataFrame): DataFrame containing node information.
            edges_df_with_line_type (pd.DataFrame): DataFrame containing edge information with line or arrow type.
            tips_df (pd.DataFrame): DataFrame containing tip information.
            tails_df (pd.DataFrame): DataFrame containing tail information.
            iou_threshold (float): Threshold for IoU to consider edge and tip overlap.

        Returns:
            pd.DataFrame: A DataFrame with updated edge information including assigned nodes.
        """
        edges_df_with_line_type['node_a'] = 'none'
        edges_df_with_line_type['node_b'] = 'none'
        edges_df_with_line_type['destination_node'] = 'none'

        for index, edge in edges_df_with_line_type.iterrows():
            if edge['line_or_arrow'] == 'arrow':
                edge_box = [edge['xmin'], edge['ymin'], edge['xmax'], edge['ymax']]
                found_tail = False
                for _, tip in tips_df.iterrows():
                    tip_box = [tip['xmin'], tip['ymin'], tip['xmax'], tip['ymax']]
                    iou = self.calculate_iou(edge_box, tip_box)
                    if iou > iou_threshold:
                        tip_center = [(tip_box[0] + tip_box[2]) / 2, (tip_box[1] + tip_box[3]) / 2]
                        destination_node = self.find_closest_node(tip_box, nodes_df)
                        edges_df_with_line_type.at[index, 'destination_node'] = destination_node
                        break

                if edges_df_with_line_type.at[index, 'destination_node'] != 'none':
                    for _, tail in tails_df.iterrows():
                        tail_box = [tail['xmin'], tail['ymin'], tail['xmax'], tail['ymax']]
                        iou = self.calculate_iou(edge_box, tail_box)
                        # logger.info(f"checking iou threhshould {iou}")
                        if iou > iou_threshold:
                            found_tail = True
                            tail_center = [(tail_box[0] + tail_box[2]) / 2, (tail_box[1] + tail_box[3]) / 2]
                            node_a = self.find_closest_node(tail_box, nodes_df)
                            edges_df_with_line_type.at[index, 'node_a'] = node_a
                            edges_df_with_line_type.at[index, 'node_b'] = edges_df_with_line_type.at[index, 'destination_node']
                            break

                if not found_tail:
                    edges_df_with_line_type.at[index, 'node_a'] = 'none'
                    edges_df_with_line_type.at[index, 'node_b'] = 'none'
                    edges_df_with_line_type.at[index, 'destination_node'] = 'none'

        return edges_df_with_line_type
    
    def calculate_min_distance(self,box1, box2):
        """
        Calculate the minimum distance between two bounding boxes.

        This method calculates the minimum horizontal and vertical distances between two bounding boxes and
        returns the Euclidean distance between these points.

        Args:
            box1 (list): The first bounding box [xmin, ymin, xmax, ymax].
            box2 (list): The second bounding box [xmin, ymin, xmax, ymax].

        Returns:
            float: The minimum distance between the two bounding boxes.
        """
        horiz_dist_min = max(0, max(box1[0] - box2[2], box2[0] - box1[2]))
        vert_dist_min = max(0, max(box1[1] - box2[3], box2[1] - box1[3]))
        return np.sqrt(horiz_dist_min**2 + vert_dist_min**2)


    #### update the NULL for the detected connected edges between two nodes
    def assign_undetermined_nodes_to_edges(self,
                                           edges_df_with_partial_determined_nodes, 
                                           nodes_df, 
                                           max_distance_px=10, 
                                           max_limit_px=500,
                                           step_px=10):
        """
        Assign undetermined nodes to edges by finding the two closest nodes within a specified distance.

        This method iteratively expands the search radius until it finds at least two nodes within the specified
        maximum distance. It then assigns these nodes to the edges.

        Args:
            edges_df_with_partial_determined_nodes (pd.DataFrame): DataFrame with edges partially determined.
            nodes_df (pd.DataFrame): DataFrame containing node information.
            max_distance_px (int): Initial maximum distance to search for nodes.
            max_limit_px (int): Maximum distance limit for node search.
            step_px (int): Step size for expanding the search radius.

        Returns:
            pd.DataFrame: A DataFrame with edges fully determined.
        """
        for index, edge in edges_df_with_partial_determined_nodes.iterrows():
            if edge['node_a'] == 'none':  # Checking if node_a is 'none'
                distance_px = max_distance_px
                nearby_nodes = []

                # Keep expanding the search radius until at least two nodes are found or the max limit is reached
                while len(nearby_nodes) < 2 and distance_px <= max_limit_px:
                    nearby_nodes.clear()
                    for _, node in nodes_df.iterrows():
                        # Calculate the minimum distance between edge and node bounding boxes
                        # Considering both horizontal and vertical directions
                        horiz_dist_min = max(0, max(edge['xmin'] - node['xmax'], node['xmin'] - edge['xmax']))
                        vert_dist_min = max(0, max(edge['ymin'] - node['ymax'], node['ymin'] - edge['ymax']))
                        min_distance = np.sqrt(horiz_dist_min**2 + vert_dist_min**2)

                        if min_distance <= distance_px:
                            node_center_x = (node['xmin'] + node['xmax']) / 2
                            node_center_y = (node['ymin'] + node['ymax']) / 2
                            nearby_nodes.append((node['id'], node_center_x, node_center_y))

                    # Increase the search radius for the next iteration if needed
                    if len(nearby_nodes) < 2:
                        distance_px += step_px

                # Find the two farthest nodes from those that are nearby
                if len(nearby_nodes) >= 2:
                    max_distance = 0
                    node_pair = (None, None)
                    for i in range(len(nearby_nodes)):
                        for j in range(i + 1, len(nearby_nodes)):
                            node1 = nearby_nodes[i]
                            node2 = nearby_nodes[j]
                            node_distance = np.sqrt((node1[1] - node2[1])**2 + (node1[2] - node2[2])**2)
                            if node_distance > max_distance:
                                max_distance = node_distance
                                node_pair = (node1[0], node2[0])
                    edges_df_with_partial_determined_nodes.at[index, 'node_a'] = node_pair[0]
                    edges_df_with_partial_determined_nodes.at[index, 'node_b'] = node_pair[1]

        return edges_df_with_partial_determined_nodes
    
    #### upadte the NULL vlaue of the destination node
    
    def determine_destination_node(self,
                                   edges_df_with_determined_nodes,
                                   nodes_df, 
                                   tips_df):
        """
        Determine the destination node for each edge by finding the closest tip.

        This method finds the closest tip for each edge and assigns the nearest node to the tip as the destination
        node. It updates the edge DataFrame with the ID of the destination node.

        Args:
            edges_df_with_determined_nodes (pd.DataFrame): DataFrame with edges fully determined.
            nodes_df (pd.DataFrame): DataFrame containing node information.
            tips_df (pd.DataFrame): DataFrame containing tip information.

        Returns:
            pd.DataFrame: A DataFrame with updated edge information including the destination node.
        """
        # Ensure we are working with copies of data to avoid modifying original dataframes outside this function
        edges_df_with_determined_nodes = edges_df_with_determined_nodes.copy()
        nodes_df = nodes_df.set_index('id')  # This allows for quick access by node ID

        edges_df_with_determined_nodes['destination_node'] = None
        


        for index, edge in edges_df_with_determined_nodes.iterrows():
            if edge['line_or_arrow'] == 'arrow' and edge['node_a'] !='none' and edge['node_b'] !='none':
                # Find the closest tip for this edge
                edge_box = [edge['xmin'], edge['ymin'], edge['xmax'], edge['ymax']]
                closest_tip = None
                min_distance_to_tip = float('inf')

                for _, tip in tips_df.iterrows():
                    tip_box = [tip['xmin'], tip['ymin'], tip['xmax'], tip['ymax']]
                    distance = self.calculate_min_distance(edge_box, tip_box)
                    if distance < min_distance_to_tip:
                        min_distance_to_tip = distance
                        closest_tip = tip_box

                if closest_tip is not None:
                    # Calculate distance from closest tip to node_a and node_b
                    node_a_box = [nodes_df.loc[edge['node_a'], 'xmin'], nodes_df.loc[edge['node_a'], 'ymin'],
                                  nodes_df.loc[edge['node_a'], 'xmax'], nodes_df.loc[edge['node_a'], 'ymax']]
                    node_b_box = [nodes_df.loc[edge['node_b'], 'xmin'], nodes_df.loc[edge['node_b'], 'ymin'],
                                  nodes_df.loc[edge['node_b'], 'xmax'], nodes_df.loc[edge['node_b'], 'ymax']]

                    distance_to_node_a = self.calculate_min_distance(closest_tip, node_a_box)
                    distance_to_node_b = self.calculate_min_distance(closest_tip, node_b_box)

                    # Assign the closer node as the destination node
                    edges_df_with_determined_nodes.at[index, 'destination_node'] = edge['node_a'] if distance_to_node_a < distance_to_node_b else edge['node_b']
                    
        edges_df_with_determined_nodes = edges_df_with_determined_nodes[
        (edges_df_with_determined_nodes['node_a'] != 'none') & 
        (edges_df_with_determined_nodes['node_b'] != 'none')]

        return edges_df_with_determined_nodes
    
    def analyze_image(self, bbox):
        """
        Analyze the image within a bounding box using AWS Textract.

        This method crops the image to the specified bounding box and uses AWS Textract to extract text
        from the cropped image.

        Args:
            bbox (tuple): The bounding box (xmin, ymin, xmax, ymax) to crop and analyze.

        Returns:
            str: The recognized text within the bounding box, or 'unrecognized' if no text is found.
        """
        with self.image_data as img:
            # Check if the image is in CMYK or another non-RGB format and convert if necessary
            if img.mode not in ['RGB', 'RGBA']:
                img = img.convert('RGB')

            cropped_img = img.crop(bbox)
            with io.BytesIO() as output:
                cropped_img.save(output, format='PNG')
                image_bytes = output.getvalue()

        response = self.textract_client.analyze_document(
            Document={'Bytes': image_bytes},
            FeatureTypes=['TABLES', 'FORMS']  # Assuming you might also want to extract forms
        )

        detected_lines = []
        for item in response['Blocks']:
            if item['BlockType'] == 'LINE' and 'Text' in item and len(item['Text']) > 2:
                detected_lines.append((item['Text'], item['Confidence']))

        if not detected_lines:
            return 'unrecognized'

        # Join detected lines and return the resulting string
        return ' '.join([text for text, _ in detected_lines])

    def apply_ocr_to_nodes_df(self,nodes_df):
        """
        Apply OCR to each node in the DataFrame to extract text.

        This method iterates through each node in the DataFrame, applies OCR to the node's bounding box,
        and adds the recognized text to a new 'text' column.

        Args:
            nodes_df (pd.DataFrame): DataFrame containing node information.

        Returns:
            pd.DataFrame: A DataFrame with an additional 'text' column containing the recognized text for each node.
        """
        nodes_df['text'] = nodes_df.apply(lambda row: self.analyze_image((row['xmin'], row['ymin'], row['xmax'], row['ymax'])), axis=1)
        return nodes_df
    
    
    def get_font_size(self, nodes_df):
        """
        Assign font size to each node based on its bounding box height.

        This method calculates the height of each node's bounding box and normalizes it to assign a font size.

        Args:
            nodes_df (pd.DataFrame): DataFrame containing node information.

        Returns:
            pd.DataFrame: A DataFrame with an additional 'font_size' column containing the font size for each node.
        """
    
        nodes_df['font_size'] = nodes_df.ymax - nodes_df.ymin

        # Check if there's more than one row
        if len(nodes_df) > 1:
            nodes_df['font_size'] = (nodes_df['font_size'] - nodes_df['font_size'].mean()) / (nodes_df['font_size'].std() + 1e-6)
        else:
            # Handle single-row scenario
            nodes_df['font_size'] = 0  # Or any other logic you deem fit for single rows

        nodes_df['font_size'] = (nodes_df['font_size'].apply(lambda x: round(x)) + 10).astype(int)

        return nodes_df
    
    def extract_feature(self):
        """
        Extract features from the image and process detections to generate nodes and edges DataFrames.

        This method performs the following steps:
        1. Predict and filter detections using the YOLO model.
        2. Extract initial graph structures (nodes, edges, tips, tails) from filtered predictions.
        3. Process edges to assign closest nodes around edge tips and tails.
        4. Assign undetermined nodes to edges.
        5. Determine destination nodes for edges.
        6. Apply OCR to nodes to extract text.
        7. Assign font size to nodes.
        8. Optionally delete the temporary image file if not predicting from local.

        Returns:
            tuple: A tuple containing the processed nodes DataFrame, edges DataFrame, and a message.
        """
        message = "Successfully extracted mind map features"
        try:
            logger.info("Starting feature extraction process.")
            
            start_time = time.time()
            logger.info("Predicting and filtering detections.")
            
            # Initial prediction
            filtered_predictions_df = self.predict_and_filter_detections()
            
            # Check if filtered nodes or edges are empty, and retry with lower thresholds if necessary
            retry = False
            if filtered_predictions_df.empty or \
            filtered_predictions_df[filtered_predictions_df['class'] == 3].empty or \
            filtered_predictions_df[filtered_predictions_df['class'] == 0].empty:
                logger.info("Filtered nodes or edges are empty, lowering model thresholds and retrying.")
                self.model_thresholds = {0: 0.1, 1: 0.1, 2: 0.1, 3: 0.1}
                filtered_predictions_df = self.predict_and_filter_detections()
                retry = True
            
            # Extract initial graph structures
            logger.info("Extracting initial graph structures.")
            filtered_nodes_df, filtered_edges_df, filtered_tips_df, filtered_tails_df = self.initial_process_detections(filtered_predictions_df)
            
            # If retry was performed, log the results
            if retry:
                logger.info(f"Retry results: filtered_nodes_df: {len(filtered_nodes_df)}, filtered_edges_df: {len(filtered_edges_df)}")
            
            # Continue with processing edges and nodes as usual
            logger.info("Assigning closest nodes around edge tips and edge tails to the edges.")
            edges_df_with_partial_determined_nodes = self.assign_closest_nodes_around_tips_and_tails_to_edges(filtered_nodes_df, filtered_edges_df, filtered_tips_df, filtered_tails_df)
            
            logger.info("Assigning undetermined nodes to edges.")
            edges_df_with_determined_nodes = self.assign_undetermined_nodes_to_edges(edges_df_with_partial_determined_nodes, filtered_nodes_df)
            
            logger.info(f"Checking edges df with determined_nodes {edges_df_with_determined_nodes}")
            logger.info("Determining destination nodes for edges.")
            edges_df = self.determine_destination_node(edges_df_with_determined_nodes, filtered_nodes_df, filtered_tails_df)
            
            logger.info("Applying OCR to nodes.")
            nodes_df = self.apply_ocr_to_nodes_df(filtered_nodes_df)
            
            logger.info("Assigning font size to nodes.")
            nodes_df = self.get_font_size(nodes_df)
            
            bucket_name = self.image_file_path.split("gs://")[-1].split("/")[0]
            image_file_name = "/".join(self.image_file_path.split("gs://")[-1].split("/")[1:])
            logger.info(f"Checking the extracted bucket_name {bucket_name} and image_file_name {image_file_name}")
            
            logger.info("Detecting colour for nodes.")
            nodes_df = nodes_addcolor(nodes_df, self.image_data)
            nodes_df.rename(columns={'id': 'node_id'}, inplace=True)
            
            logger.info("Assigning the nodes hierarchy.")
            nodes_hierarchy_checker = DetermineNodesHierarchy(nodes_df, edges_df, bucket_name, image_file_name, OPENAI_API_KEY)
            nodes_hierarchy = nodes_hierarchy_checker.process()
            final_nodes_df = nodes_df.copy()
            final_nodes_df['node_level'] = final_nodes_df['node_id'].map(nodes_hierarchy)
            
            end_time = time.time()
            logger.info(f"Feature extraction process completed in {end_time - start_time:.2f} seconds.")   
            
            return final_nodes_df, edges_df, message

        except Exception as e:
            error_message = f"Error during feature extraction: {str(e)}"
            logger.error(error_message)
            return pd.DataFrame(), pd.DataFrame(), error_message


    def generate_json_output(self,
                                nodes_df,
                                edges_df,
                                image_file,
                                user_id,
                                message):
            """
            Generate a JSON output from the nodes and edges DataFrames.
            This method creates a JSON structure representing the graph, including nodes, edges, image information,
            user ID, and a message.
            Args:
                nodes_df (pd.DataFrame): DataFrame containing node information.
                edges_df (pd.DataFrame): DataFrame containing edge information.
                image_file (str): The name of the image file.
                user_id (str): The user ID.
                message (str): Additional message to include in the JSON output.
            Returns:
                dict: A dictionary representing the graph, including nodes, edges, image information, user ID, and message.
            """
            # Create nodes dictionary
            image_id = str(uuid.uuid4())
            nodes = []
            if not nodes_df.empty:
                for index, row in nodes_df.iterrows():
                    node_id = row['node_id']
                    attributes = {
                        'position': {
                            'x': (row['xmin'] + row['xmax']) / 2,
                            'y': (row['ymin'] + row['ymax']) / 2
                        },
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
            if not edges_df.empty:
                for index, row in edges_df.iterrows():
                    edge = {
                        'node_a': row['node_a'],
                        'node_b': row['node_b'],
                        'bbox': {
                            'xmin': row['xmin'],
                            'ymin': row['ymin'],
                            'xmax': row['xmax'],
                            'ymax': row['ymax']
                        }
                    }
                    if pd.isna(row['destination_node']):
                        destination_node = 'None'
                    else:
                        destination_node = row['destination_node']
                    edge_info = {
                        'edge': edge,
                        'destination_node': destination_node,
                        'thickness': 0,  # float(row['thickness'])
                        'length': 0  # float(row['length'])
                    }
                    edges.append(edge_info)
            # Create graph dictionary
            graph = {
                'image_id': image_id,
                'user_id': user_id,
                'image_name': image_file,
                'graph': {
                    'nodes': nodes,
                    'edges': edges
                },
                'message': message
            }
            return graph
