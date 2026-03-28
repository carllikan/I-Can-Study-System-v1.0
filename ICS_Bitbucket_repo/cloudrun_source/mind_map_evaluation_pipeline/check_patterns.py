import re  
import json
import io
from gpt4_response import *
from PIL import Image, ImageFile
import logging
from transformers import AutoImageProcessor, AutoModelForObjectDetection
import torch
from dotenv import load_dotenv
load_dotenv()
HF_ACCESS_TOKEN = gcp_get_secret(project_number,func_conf.get('hf_access_token', 'hf_access_token_namee' ))

class DetectPatterns():
    def __init__(self,graph_features,bucket_name,image_name):
        """
        Initializes the DetectPatterns class.

        Parameters:
        graph_features (dict): A dictionary containing the features of the graph (nodes and edges).
        bucket_name (str): The name of the Google Cloud Storage bucket.
        image_name (str): The name of the image file in the bucket.
        """
        # logger.warning(HF_ACCESS_TOKEN)
        self.snc_checkpoint = 'AddAxis/detect_single_node_chain'
        self.island_checkpoint = 'AddAxis/detect_island'
        self.snc_image_processor = AutoImageProcessor.from_pretrained(self.snc_checkpoint,token =HF_ACCESS_TOKEN)
        self.snc_model = AutoModelForObjectDetection.from_pretrained(self.snc_checkpoint,token =HF_ACCESS_TOKEN)
        self.island_image_processor = AutoImageProcessor.from_pretrained(self.island_checkpoint,token =HF_ACCESS_TOKEN)
        self.island_model = AutoModelForObjectDetection.from_pretrained(self.island_checkpoint,token =HF_ACCESS_TOKEN)
        self.graph_features = graph_features
        self.bucket_name = bucket_name
        self.image_name = image_name

        
    def _check_too_wordy(self,threshold=0.25):
        """
        Checks if the mind map is too wordy based on specified conditions.

        Parameters:
        threshold (float): The threshold ratio for determining wordiness. Default is 0.25.

        Returns:
        bool: True if the mind map is too wordy, False otherwise.
        """
        
        nodes_features = self.graph_features.get("nodes", [])

        # Extract texts from nodes based on the structure
        texts = [node['attributes']['text'] for node in nodes_features]

        # Condition 1: At least 25% of nodes have more than 5 words
        nodes_with_more_than_5_words = sum(1 for text in texts if len(text.split()) >= 5)
        condition_1 = nodes_with_more_than_5_words / len(nodes_features) >= threshold

        # Condition 2: 15% of the words on the mindmap are full sentences or paragraphs
        total_words = sum(len(text.split()) for text in texts)
        total_sentences_or_paragraphs = sum(1 for text in texts if "." in text or "?" in text or "!" in text)
        condition_2 = (total_sentences_or_paragraphs / total_words) if total_words != 0 else 0  # Avoid zero division
        condition_2_met = condition_2 >= 0.15

        return condition_1 or condition_2_met

    def _check_lines_over_arrows(self,threshold=0.70):
        """
        Checks if the ratio of lines over arrows in the mind map exceeds a specified threshold.

        Parameters:
        threshold (float): The threshold ratio for lines over arrows. Default is 0.70.

        Returns:
        bool: True if the ratio exceeds the threshold, False otherwise.
        """
        edges_features = self.graph_features.get("edges", [])

        # Count the edges which are lines (destination_node is "None")
        line_count = sum(1 for edge in edges_features if edge.get("destination_node") == "None")

        return line_count / len(edges_features) >= threshold

    def _check_single_node_chain(self):
        """
        Checks for the presence of a 'single node chain' pattern in the mind map.

        Returns:
        bool: True if a single node chain is detected, False otherwise.
        """

        edges_features = self.graph_features.get("edges", [])

        # Create a dictionary to keep track of node connections
        node_connections = {}

        # Create the node connections graph
        for edge in edges_features:
            node_a, node_b = edge['edge']['node_a'], edge['edge']['node_b']
            node_connections.setdefault(node_a, set()).add(node_b)
            node_connections.setdefault(node_b, set()).add(node_a)

        # Find nodes with only two connections
        potential_single_nodes = {node for node, connections in node_connections.items() if len(connections) == 2}

        # Set to keep track of visited nodes to avoid cycles
        visited = set()

        # Function to traverse the chain
        def traverse_chain(node):
            if node in visited or node not in potential_single_nodes:
                return []
            visited.add(node)
            connections = node_connections[node]
            if len(connections) != 2:
                return [node]
            # Take one of the connected nodes and continue the chain, only if it hasn't been visited
            next_nodes = connections - visited
            if not next_nodes:
                return [node]  # End of chain reached
            next_node = next_nodes.pop()
            return [node] + traverse_chain(next_node)

        # Check each potential chain
        for node in potential_single_nodes:
            if node not in visited:
                chain = traverse_chain(node)
                if len(chain) >= 3:  # Chain should have at least 3 nodes
                    return True

        return False
    
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

    def _check_single_node_chain_yolo(self,threshold = 0.5):
        """
        Checks for the presence of a 'single node chain' pattern in the mind map with yolo model

        Returns:
        bool: True if a single node chain is detected, False otherwise.
        """

        """
        Determines if the mind map image is a screenshot using a Hugging Face object detection model.

        Returns:
        tuple: A tuple containing the detection results and a boolean indicating whether the image is identified as a screenshot (True) or not (False).
        """
        bytes_data = self.read_image_data_from_gcs()
        image_data = io.BytesIO(bytes_data)

        # # Open the image with PIL
        image = Image.open(image_data)
        if image.format == "PNG":
            image = image.convert("RGB") 
        inputs = self.snc_image_processor(images=image, return_tensors="pt")
        outputs = self.snc_model(**inputs)
        
        target_sizes = torch.tensor([image.size[::-1]])
        results = self.snc_image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold = threshold)[0]
        if len(results['scores'])>0:
            return True
        else:
            return False
    
    def _check_insufficient_chunking(self):
        """
        Checks for insufficient chunking in the mind map, based on the number of connections a node has.

        Returns:
        bool: True if any node has more than four outbound connections, indicating insufficient chunking.
        """
        edges_features = self.graph_features.get("edges", [])

        # Dictionary to count outbound and inbound connections
        outbound_connections = {}
        inbound_connections = {}

        for edge in edges_features:
            node_a = edge['edge']['node_a']
            node_b = edge['edge']['node_b']
            destination = edge.get('destination_node', None)

            # If destination_node is not None, track outbound and inbound connection
            if destination is not None:
                source_node = node_b if destination == node_a else node_a

                # Track outbound
                if source_node not in outbound_connections:
                    outbound_connections[source_node] = 0
                outbound_connections[source_node] += 1

                # Track inbound
                if destination not in inbound_connections:
                    inbound_connections[destination] = 0
                inbound_connections[destination] += 1

        for _, count in outbound_connections.items():
            # If outbound connections for any node exceed 4, return True
            if count > 4:
                return True

        return False
    
    def _check_question_chunked(self):
        """
        Checks if questions are appropriately chunked in higher hierarchy nodes of the mind map.

        Returns:
        bool: True if questions are properly chunked, False otherwise.
        """
        nodes_features = self.graph_features.get("nodes", [])

        # Regex pattern to match standalone words 'what' and 'how'
        pattern = r'\b(what|how)\b'

        for node in nodes_features:
            text = node['attributes']['text'].lower()  # Convert to lowercase for consistent comparison
            level = node['attributes']['node_level']

            # Check if the node is of higher hierarchy (level 1 or 2)
            # and if it contains a question mark or the standalone words "what" or "how".
            if level in [1, 2] and ('?' in text or re.search(pattern, text)):
                return True

        return False
    
    def _check_segmental_mapping(self,
                                font_size_threshold=0.25,  
                                connection_threshold=3):
        """
        Checks for proper segmental mapping in the mind map based on font size differences and node connections.

        Parameters:
        font_size_threshold (float): The threshold ratio for font size differences.
        connection_threshold (int): The threshold for the number of connections.

        Returns:
        bool: True if segmental mapping criteria are not met, False otherwise.
        """
        # Extract nodes and edges from graph_features
        nodes_features = self.graph_features.get('nodes', [])
        edges_features = self.graph_features.get('edges', [])

        # Create a connection map
        connection_map = {}
        for edge in edges_features:
            node_a = edge['edge']['node_a']
            node_b = edge['edge']['node_b']

            if node_a not in connection_map:
                connection_map[node_a] = set()
            if node_b not in connection_map:
                connection_map[node_b] = set()

            connection_map[node_a].add(node_b)
            connection_map[node_b].add(node_a)

        # Get hierarchy levels for each node
        node_levels = {node['node_id']: node['attributes']['node_level'] for node in nodes_features}

        # Identify highest level nodes (level 1 in this case) and exclude disconnected nodes
        highest_level_nodes = [node for node, level in node_levels.items() if level == 1 and node in connection_map]

        unique_levels_counts = []
        for node in highest_level_nodes:
            unique_levels_reached = get_unique_levels(node, node_levels, connection_map)
            ## checking the print for helping fine tune the the threshold if needed
            # logging.info(f"Unique levels: Node {node} at highest level 1 reaches unique levels: {unique_levels_reached}")
            unique_levels_counts.append(len(unique_levels_reached))

        if unique_levels_counts:
            max_levels = max(unique_levels_counts)
            min_levels = min(unique_levels_counts)

            if max_levels - min_levels >= connection_threshold:
                ## checking the print for helping fine tune the the threshold if needed
                # logging.info(f"The difference between max unique level and mini unique level greater than {connection_threshold}")
                return True

        # Check font size difference for the complete mindmap
        font_sizes = [node['attributes']['font_size'] for node in nodes_features]
        if abs(max(font_sizes) - min(font_sizes)) / max(font_sizes) > font_size_threshold:
            ## checking the print for helping fine tune the the threshold if needed
            # logging.info(f"The font size threshold value is greater than given threshold.")
            return True

        return False
    
    def _check_unclear_backbone(self, 
                                num_high_level_nodes=7, 
                                level0_percentage_threshold=0.5):
        """
        Checks for an unclear backbone in the mind map based on the distribution of node levels.

        Parameters:
        num_high_level_nodes (int): The threshold number of high-level nodes.
        level0_percentage_threshold (float): The percentage threshold for level 0 nodes.

        Returns:
        bool: True if the backbone is unclear, False otherwise.
        """
        # Extract nodes and edges from graph_features
        nodes_features = self.graph_features.get('nodes', [])
        edges_features = self.graph_features.get('edges', [])

        # Get all unique node levels present in the nodes_features
        unique_levels = set(node['attributes']['node_level'] for node in nodes_features)

        # If all nodes are of level 0 or level 1, it's hard to determine the hierarchy
        if unique_levels == {0} or unique_levels == {1}:
            ## checking the print for helping fine tune the the threshold if needed
            # logging.info("all nodes too high or disconnected")
            return True

        # Count the number of nodes with level 0
        level_0_count = sum(1 for node in nodes_features if node['attributes']['node_level'] == 0)

        # If the ratio of level 0 nodes to total nodes exceeds the percentage threshold, it's unclear
        if level_0_count / len(nodes_features) > level0_percentage_threshold:
            ## checking the print for helping fine tune the the threshold if needed
            # logging.info("disconnected nodes over 50%")
            return True

        # Get the number of highest hierarchy nodes
        level_1_nodes = [node['node_id'] for node in nodes_features if node['attributes']['node_level'] == 1]

        # If the number of level 1 nodes exceeds the threshold, it's unclear
        if len(level_1_nodes) >= num_high_level_nodes:
            ## checking the print for helping fine tune the the threshold if needed
            # logging.info("high level nodes more than 7")
            return True

        # Check the type of connections between level 1 nodes: lines vs arrows
        lines_count = sum(1 for edge in edges_features if
                          edge['destination_node'] is None and
                          edge['edge']['node_a'] in level_1_nodes and
                          edge['edge']['node_b'] in level_1_nodes)

        arrows_count = sum(1 for edge in edges_features if
                           edge['destination_node'] is not None and
                           edge['edge']['node_a'] in level_1_nodes and
                           edge['edge']['node_b'] in level_1_nodes)

        # If there are more lines connecting level 1 nodes than arrows, it's unclear
        if lines_count > arrows_count:

            return True

        return False


    def _check_islands_yolo(self,threshold = 0.1):
            """
            Checks for the presence of a 'single node chain' pattern in the mind map with yolo model

            Returns:
            bool: True if a single node chain is detected, False otherwise.
            """

            """
            Determines if the mind map image is a screenshot using a Hugging Face object detection model.

            Returns:
            tuple: A tuple containing the detection results and a boolean indicating whether the image is identified as a screenshot (True) or not (False).
            """
            bytes_data = self.read_image_data_from_gcs()
            image_data = io.BytesIO(bytes_data)

            # # Open the image with PIL
            image = Image.open(image_data)
            if image.format == "PNG":
                image = image.convert("RGB") 
            inputs = self.island_image_processor(images=image, return_tensors="pt")
            outputs = self.island_model(**inputs)
            
            target_sizes = torch.tensor([image.size[::-1]])
            results = self.island_image_processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold = threshold)[0]
            if len(results['scores'])>0:

                return True
            else:
                return False
    def _check_islands(self, threshold=0.28):
        """
        Checks for the presence of 'islands' in the mind map based on font size differences.

        Parameters:
        threshold (float): The threshold ratio for determining the presence of islands.

        Returns:
        bool: True if islands are detected, False otherwise.
        """
        
        # Extract nodes from graph_features
        nodes_features = self.graph_features.get('nodes', [])

        # Determine the font size for the highest and lowest level of hierarchy
        highest_level = max(node['attributes']['node_level'] for node in nodes_features)
        lowest_level = min(node['attributes']['node_level'] for node in nodes_features)

        highest_level_font_size = max(
            node['attributes']['font_size'] for node in nodes_features if node['attributes']['node_level'] == highest_level)
        lowest_level_font_size = min(
            node['attributes']['font_size'] for node in nodes_features if node['attributes']['node_level'] == lowest_level)

        # Check if (max-min)/max is greater than 30% 
        return (highest_level_font_size - lowest_level_font_size)/highest_level_font_size > threshold

    def _check_spiderwebbing(self):
        """
        Checks for a 'spiderwebbing' pattern in the mind map based on lateral connections.

        Returns:
        bool: True if spiderwebbing is detected, False otherwise.
        """
        nodes = self.graph_features['nodes']
        edges = self.graph_features['edges']

        # Convert nodes to dictionary for easy access
        node_dict = {node['node_id']: node for node in nodes}

        # Check for lateral connections
        lateral_connections = {}
        for edge in edges:
            node_a = edge['edge']['node_a']
            node_b = edge['edge']['node_b']

            level_a = node_dict[node_a]['attributes']['node_level']
            level_b = node_dict[node_b]['attributes']['node_level']

            if level_a == level_b:
                if level_a not in lateral_connections:
                    lateral_connections[level_a] = 0
                lateral_connections[level_a] += 1

        total_edges = len(edges)
        for count in lateral_connections.values():
            if count / total_edges >= 0.9:
                return True

        return False

    def _check_waterfalling(self):
        """
        Checks for a 'waterfalling' pattern in the mind map based on lateral connections at higher levels.

        Returns:
        bool: True if waterfalling is not detected, False otherwise.
    """
        nodes = self.graph_features['nodes']
        edges = self.graph_features['edges']

        node_dict = {node['node_id']: node for node in nodes}

        # Check for lateral connections
        lateral_connections = {}
        for edge in edges:
            node_a = edge['edge']['node_a']
            node_b = edge['edge']['node_b']

            level_a = node_dict[node_a]['attributes']['node_level']
            level_b = node_dict[node_b]['attributes']['node_level']

            if level_a == level_b and level_a not in [0, 1]:
                if level_a not in lateral_connections:
                    lateral_connections[level_a] = 0
                lateral_connections[level_a] += 1

        total_edges = len(edges)
        for count in lateral_connections.values():
            if count / total_edges > 0.1:
                return False

        return True
    
    def _check_unclear_backbone_with_gpt4(self):
        """
        Checks for an unclear backbone in the mind map using GPT-4 analysis.

        Returns:
        bool: True if GPT-4 analysis suggests an unclear backbone, False otherwise.
        """
        response = detect_unclear_backbone_with_gpt4(self.image_name,self.bucket_name)
        if response.get("unclear_backbone")=="true":
            return True
        else:
            return False
        
    
    def _check_single_node_chain_with_gpt4(self):
        """
        Checks for a 'single node chain' pattern in the mind map using GPT-4 analysis.

        Returns:
        bool: True if GPT-4 analysis detects a single node chain, False otherwise.
        """
        response = detect_single_node_chain_with_gpt4(self.image_name,self.bucket_name)
        if response.get("single_node_chain")=="true":
            return True
        else:
            return False
        
    def detect_spiderwebbing_yolov9(nodes_df, edges_df, length_threshold=100, overlap_threshold=3, same_level_connection_threshold=0.7):
        """
        Detect spiderwebbing pattern in the mind map.
        Args:
            nodes_df (pd.DataFrame): DataFrame containing node information with columns ['node_id', 'xmin', 'ymin', 'xmax', 'ymax', 'node_level'].
            edges_df (pd.DataFrame): DataFrame containing edge information with columns ['node_a', 'node_b', 'xmin', 'ymin', 'xmax', 'ymax'].
            length_threshold (int): The threshold for considering an edge as long.
            overlap_threshold (int): The threshold for considering an edge as overlapping.
            same_level_connection_threshold (float): The threshold ratio for considering lateral connections as high.
        Returns:
            bool: True if spiderwebbing is detected, False otherwise.
        """
        def calculate_length(xmin, ymin, xmax, ymax):
            return ((xmax - xmin) ** 2 + (ymax - ymin) ** 2) ** 0.5
        def check_overlap(edge1, edge2):
            A, B = (edge1['xmin'], edge1['ymin']), (edge1['xmax'], edge1['ymax'])
            C, D = (edge2['xmin'], edge2['ymin']), (edge2['xmax'], edge2['ymax'])
            return check_lines_intersect(A, B, C, D)
        same_level_connections = 0
        long_connections = 0
        overlapping_connections = 0
        # Check for same level lateral connections and calculate their lengths
        for _, edge in edges_df.iterrows():
            node_a_level = nodes_df.loc[nodes_df['node_id'] == edge['node_a'], 'node_level'].values[0]
            node_b_level = nodes_df.loc[nodes_df['node_id'] == edge['node_b'], 'node_level'].values[0]
            if node_a_level == node_b_level:
                same_level_connections += 1
                if calculate_length(edge['xmin'], edge['ymin'], edge['xmax'], edge['ymax']) > length_threshold:
                    long_connections += 1
                for _, other_edge in edges_df.iterrows():
                    if edge['node_a'] != other_edge['node_a'] or edge['node_b'] != other_edge['node_b']:
                        if check_overlap(edge, other_edge):
                            overlapping_connections += 1
        total_edges = len(edges_df)
        same_level_connection_ratio = same_level_connections / total_edges if total_edges else 0
        long_connection_ratio = long_connections / same_level_connections if same_level_connections else 0
        overlap_ratio = overlapping_connections / same_level_connections if same_level_connections else 0
        # Detect spiderwebbing based on the defined thresholds
        if same_level_connection_ratio > same_level_connection_threshold and (long_connection_ratio > 0.5 or overlap_ratio > overlap_threshold):
            return True
        return False
    def check_lines_intersect(A, B, C, D):
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)
    
    def _check_spiderwebbing_with_gpt4(self):
        """
        Checks for a 'spiderwebbing' pattern in the mind map using GPT-4 analysis.

        Returns:
        bool: True if GPT-4 analysis detects spiderwebbing, False otherwise.
        """
        response = detect_spiderwebbing_with_gpt4(self.image_name,self.bucket_name)
        if response.get("spiderwebbing")=="true":
            return True
        else:
            return False
        
    
    def _check_highest_hierarchy_nodes_with_gpt4(self):
        """
        Checks for the highest hierarchy nodes in the mind map using GPT-4 analysis.

        Returns:
        bool: True if GPT-4 analysis can determine the highest hierarchy nodes, False otherwise.
        """
        response = detect_highest_hierarchy_nodes_with_gpt4(self.image_name, self.bucket_name)
        if response.get("highest_hierarchy_nodes") =="no":
            response = False
        else:
            response = True
        return response
    def detect_patterns(self):
        """
        Detects various patterns in the mind map and consolidates the results.

        Returns:
        str: A JSON string containing the results of the pattern detection.
        """


        ################### hardcoded with the certainty based on the current accuracy ##############
        certainty_mapping = {
                'unclear backbone': 'moderate',
                "too wordy": 'high',  
                "lines over arrows": 'high',  
                "single node chain": 'moderate',  
                "insufficient chunking": 'moderate',  
                "question chunked": 'high',  
                "segmental mapping": 'moderate',  
                "islands": 'high',  
                "spiderwebbing": 'moderate',  
                "waterfalling": 'moderate'  
            }

        # Check unclear_backbone first
        unclear_backbone = self._check_unclear_backbone_with_gpt4()
        # check the highest hiearacy for further checking
        # when two checking are not aligned (i.e. hard to detect) we always want to make sure
        # it returns false positive values i.e. alwasy return unclear_backboen 
        highest_hierarchy_nodes = self._check_highest_hierarchy_nodes_with_gpt4()
        # If unclear_backbone returns True, then only check the specified functions
        if not unclear_backbone and highest_hierarchy_nodes:
             #check all functions
            logging.info("Double check if unclear backone exists passed!")
            too_wordy = self._check_too_wordy()
            lines_over_arrows = self._check_lines_over_arrows()
            single_node_chain = self._check_single_node_chain_yolo() # using gpt4
            insufficient_chunking = self._check_insufficient_chunking()
            question_chunked = self._check_question_chunked()
            segmental_mapping = self._check_segmental_mapping()
            islands = self._check_islands_yolo()
            spiderwebbing = self._check_spiderwebbing_with_gpt4() # using gpt 4
            waterfalling = self._check_waterfalling()
            
        else:
            ## 
            PATTERN_NOT_DETECT_MESSAGE='The mind map is detected as unclear backbone, this pattern would not be estimated, please modify your uploaded mind map.'
            too_wordy = self._check_too_wordy()
            lines_over_arrows = self._check_lines_over_arrows()
            single_node_chain = self._check_single_node_chain_with_gpt4() # using gpt-4
            insufficient_chunking = self._check_insufficient_chunking()
            question_chunked = PATTERN_NOT_DETECT_MESSAGE
            segmental_mapping = PATTERN_NOT_DETECT_MESSAGE
            islands = PATTERN_NOT_DETECT_MESSAGE
            spiderwebbing = PATTERN_NOT_DETECT_MESSAGE
            waterfalling = PATTERN_NOT_DETECT_MESSAGE
    ####################### SET MINDMAPS NOT EVALUATED AS FOLLOWING MESSAGE ############
        SYSTEM_MESSAGE = "This pattern is not evaluated in the current phase."
        lower_order_inquiry = SYSTEM_MESSAGE
        wheel_and_spokes = SYSTEM_MESSAGE
        
        cracked_glass = SYSTEM_MESSAGE
        flashcard_overwhelm = SYSTEM_MESSAGE
        reverse_chunking_needed = SYSTEM_MESSAGE
        circuit_gridding = SYSTEM_MESSAGE
        unshaped = SYSTEM_MESSAGE
        equation_chunked = SYSTEM_MESSAGE
        lonely_chunks = SYSTEM_MESSAGE
        intuitive_chunking_needed = SYSTEM_MESSAGE
        anti_spiderwebbing = SYSTEM_MESSAGE
        detail_stripped = SYSTEM_MESSAGE
        narrow_scope = SYSTEM_MESSAGE
        importance_checklisting = SYSTEM_MESSAGE
        system_entrenchment = SYSTEM_MESSAGE
        overscheduling = SYSTEM_MESSAGE
        microscheduling = SYSTEM_MESSAGE
        unprotected_tasks = SYSTEM_MESSAGE
        # Formatting the result as the desired JSON
        result_json = json.dumps({
                                "unclear backbone": {
                                    "pattern_existence": unclear_backbone,
                                    "certainty": certainty_mapping['unclear backbone']
                                },
                                "question chunked": {
                                    "pattern_existence": question_chunked,
                                    "certainty": certainty_mapping['question chunked']
                                },
                                "segmental mapping": {
                                    "pattern_existence": segmental_mapping,
                                    "certainty": certainty_mapping['segmental mapping']
                                },
                                "islands": {
                                    "pattern_existence": islands,
                                    "certainty": certainty_mapping['islands']
                                },
                                "spiderwebbing": {
                                    "pattern_existence": spiderwebbing,
                                    "certainty": certainty_mapping['spiderwebbing']
                                },
                                "waterfalling": {
                                    "pattern_existence": waterfalling,
                                    "certainty": certainty_mapping['waterfalling']
                                },
                                "too wordy": {
                                    "pattern_existence": too_wordy,
                                    "certainty": certainty_mapping['too wordy']
                                },
                                "lines over arrows": {
                                    "pattern_existence": lines_over_arrows,
                                    "certainty": certainty_mapping['lines over arrows']
                                },
                                "single node chain": {
                                    "pattern_existence": single_node_chain,
                                    "certainty": certainty_mapping['single node chain']
                                },
                                "insufficient chunking": {
                                    "pattern_existence": insufficient_chunking,
                                    "certainty": certainty_mapping['insufficient chunking']
                                },
                                "lower order inquiry": {
                                    "pattern_existence": lower_order_inquiry,
                                    "certainty": "none"
                                },
                                "wheel and spokes": {
                                    "pattern_existence": wheel_and_spokes,
                                    "certainty": "none"
                                },
                                "cracked glass": {
                                    "pattern_existence": cracked_glass,
                                    "certainty": "none"
                                },
                                "flashcard overwhelm": {
                                    "pattern_existence": flashcard_overwhelm,
                                    "certainty": "none"
                                },
                                "reverse chunking needed": {
                                    "pattern_existence": reverse_chunking_needed,
                                    "certainty": "none"
                                },
                                "circuit gridding": {
                                    "pattern_existence": circuit_gridding,
                                    "certainty": "none"
                                },
                                "unshaped": {
                                    "pattern_existence": unshaped,
                                    "certainty": "none"
                                },
                                "equation chunked": {
                                    "pattern_existence": equation_chunked,
                                    "certainty": "none"
                                },
                                "lonely chunks": {
                                    "pattern_existence": lonely_chunks,
                                    "certainty": "none"
                                },
                                "intuitive chunking needed": {
                                    "pattern_existence": intuitive_chunking_needed,
                                    "certainty": "none"
                                },
                                "anti-spiderwebbing": {
                                    "pattern_existence": anti_spiderwebbing,
                                    "certainty": "none"
                                },
                                "detail stripped": {
                                    "pattern_existence": detail_stripped,
                                    "certainty": "none"
                                },
                                "narrow scope": {
                                    "pattern_existence": narrow_scope,
                                    "certainty": "none"
                                },
                                "importance checklisting": {
                                    "pattern_existence": importance_checklisting,
                                    "certainty": "none"
                                },
                                "system entrenchment": {
                                    "pattern_existence": system_entrenchment,
                                    "certainty": "none"
                                },
                                "overscheduling": {
                                    "pattern_existence": overscheduling,
                                    "certainty": "none"
                                },
                                "microscheduling": {
                                    "pattern_existence": microscheduling,
                                    "certainty": "none"
                                },
                                "unprotected tasks": {
                                    "pattern_existence": unprotected_tasks,
                                    "certainty": "none"
                                }
                            })

        return result_json


def ccw(A, B, C):
    """
    Helper method to determine if three points are in a counter-clockwise position.

    Parameters:
    A, B, C (tuple): Points in the format (x, y).

    Returns:
    bool: True if the points are in a counter-clockwise position, False otherwise.
    """
#     or conter_clockwise_test
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def check_lines_intersect(A, B, C, D):
    """
    Checks if two lines intersect.

    Parameters:
    A, B, C, D (tuple): Points representing two line segments.

    Returns:
    bool: True if lines AB and CD intersect, False otherwise.
    """
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def get_unique_levels(node, node_levels, connection_map, visited=None):
    """
    Recursively identifies unique levels reachable from a given node in the mind map.

    Parameters:
    node (str): The starting node ID.
    node_levels (dict): A dictionary mapping node IDs to their levels.
    connection_map (dict): A dictionary mapping node IDs to their connected nodes.
    visited (set): A set of visited nodes to avoid cycles.

    Returns:
    set: A set of unique levels reachable from the given node.
    """
    if visited is None:
        visited = set()

    visited.add(node)
    unique_levels = {node_levels[node]}

    for conn in connection_map.get(node, []):
        if conn not in visited:
            unique_levels.update(get_unique_levels(conn, node_levels, connection_map, visited))

    return unique_levels