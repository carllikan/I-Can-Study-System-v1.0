from collections import defaultdict
from google.cloud import storage
from PIL import Image
import io
from gpt4_response import *
from fuzzywuzzy import fuzz
import re
from gcp import *
# in deployment using the following logger
logger = gcp_logger()

class DetermineNodesHierarchy:
    def __init__(self, 
                 nodes_df, 
                 connections_df, 
                 bucket_name, 
                 file_name, 
                 openai_api_key,
                 font_threshold=2, 
                 ratio_threshold=0.05, 
                 score_threshold=0.085):
        """
        Initializes the DetermineNodesHierarchy object.

        Parameters:
        nodes_df (DataFrame): A pandas DataFrame containing information about the nodes.
        connections_df (DataFrame): A pandas DataFrame containing information about the connections between nodes.
        bucket_name (str): Name of the Google Cloud Storage bucket.
        file_name (str): Name of the file in the bucket.
        openai_api_key (str): API key for OpenAI.
        font_threshold (float): Threshold for font size differences. Default is 2.
        ratio_threshold (float): Threshold for non-white pixel ratio differences. Default is 0.05.
        score_threshold (float): Threshold for scoring nodes. Default is 0.085.

        Attributes:
        hierarchy (dict): A dictionary mapping node IDs to their hierarchical level.
        """
        self.nodes_df = nodes_df
        self.connections_df = connections_df
        self.bucket_name = bucket_name
        self.file_name = file_name
        self.openai_api_key = openai_api_key
        self.font_threshold = font_threshold
        self.ratio_threshold = ratio_threshold
        self.score_threshold = score_threshold
        self.hierarchy = {node_id: -1 for node_id in self.nodes_df['node_id']}
    @staticmethod
    def _extract_bounding_boxes(nodes_df):
        """
        Extracts bounding boxes from the nodes DataFrame.

        Parameters:
        nodes_df (DataFrame): A pandas DataFrame containing information about the nodes.

        Returns:
        list: A list of bounding box coordinates.
        """
        return nodes_df[['xmin', 'ymin', 'xmax', 'ymax']].values.tolist()

    def _compute_non_white_pixel_ratio(self, bounding_boxes):
        """
        Computes the ratio of non-white pixels in the specified bounding boxes of the image.

        Parameters:
        bounding_boxes (list): A list of bounding box coordinates.

        Returns:
        list: A list of ratios of non-white pixels for each bounding box.
        """
        client = storage.Client()
        bucket = client.get_bucket(self.bucket_name)
        blob = bucket.blob(self.file_name)

        image_data = blob.download_as_string()
        bytes_io = io.BytesIO(image_data)
        img = Image.open(bytes_io)

        ratios = []
        for box in bounding_boxes:
            region = img.crop(box)
            non_white_pixels = sum(pixel != (255, 255, 255) for pixel in region.getdata())
            ratio = non_white_pixels / len(list(region.getdata()))
            ratios.append(ratio)
        return ratios

    def add_ratios_to_table(self):
        """
        Adds the computed non-white pixel ratios to the nodes DataFrame.

        Returns:
        DataFrame: Updated nodes DataFrame with non-white pixel ratios added.
        """
        bounding_boxes = self._extract_bounding_boxes(self.nodes_df)
        ratios = self._compute_non_white_pixel_ratio(bounding_boxes)
        self.nodes_df['Non_White_Ratio'] = ratios
        return self.nodes_df

    def compute_node_score(self, w_font=0.7, w_ratio=0.3):
        """
        Computes the score for each node based on font size and non-white pixel ratio.

        Parameters:
        w_font (float): Weight for the font size score. Default is 0.7.
        w_ratio (float): Weight for the non-white pixel ratio score. Default is 0.3.

        Returns:
        Series: A pandas Series containing the computed scores for each node.
        """
        font_size_score = self.nodes_df["font_size"]
        bounding_boxes = self._extract_bounding_boxes(self.nodes_df)
        non_white_ratio_score = self._compute_non_white_pixel_ratio(bounding_boxes)
        return w_font * font_size_score + w_ratio * non_white_ratio_score

    @staticmethod
    def all_similar(values, threshold):
        """
        Checks if all values in a list are similar within a specified threshold.

        Parameters:
        values (list): A list of values to check.
        threshold (float): The threshold for similarity.

        Returns:
        bool: True if values are similar, False otherwise.
        """
        return max(values) - min(values) < threshold

    @staticmethod
    def normalize_min_max(values):
        """
        Normalizes values using min-max normalization.

        Parameters:
        values (list): A list of values to normalize.

        Returns:
        list: A list of normalized values.
        """
        min_val = min(values)
        max_val = max(values)
        return [(v - min_val) / (max_val - min_val) for v in values]

    def dynamic_weights(self):
        """
        Computes dynamic weights for font size and non-white pixel ratio.

        Returns:
        tuple: A tuple containing the font weight and ratio weight.
        """
        font_sizes = self.nodes_df["font_size"]
        ratios = self.nodes_df["Non_White_Ratio"]
        font_weight, ratio_weight = self._compute_dynamic_weights(font_sizes, ratios)
        return font_weight, ratio_weight

    @staticmethod
    def compute_dynamic_weights(font_sizes, ratios):
        """
        Computes dynamic weights based on the range of font sizes and ratios.

        Parameters:
        font_sizes (list): A list of font sizes.
        ratios (list): A list of non-white pixel ratios.

        Returns:
        tuple: A tuple containing the font weight and ratio weight.
        """
        font_range = max(font_sizes) - min(font_sizes)
        ratio_range = max(ratios) - min(ratios)
        font_weight = font_range / (font_range + ratio_range)
        return font_weight, 1 - font_weight
    
    def adjust_node_levels(self):
        """
        Adjusts the hierarchy levels of nodes based on font size and color similarity.

        Returns:
        dict: A dictionary mapping node IDs to their adjusted hierarchical level.
        """
        changed = True
        while changed:
            changed = False
            unique_levels = sorted(set(self.hierarchy.values()))
            for level in unique_levels[3:]:  # Start from 2
                prev_level_nodes = [node for node, lvl in self.hierarchy.items() if lvl == level - 1]
                curr_level_nodes = [node for node, lvl in self.hierarchy.items() if lvl == level]

                # Find nodes that need to be collapsed
                nodes_to_collapse = []
                for node in curr_level_nodes:
                    node_color = self.nodes_df[self.nodes_df['node_id'] == node]['color'].iloc[0]
                    node_font_size = self.nodes_df[self.nodes_df['node_id'] == node]['font_size'].iloc[0]

                    same_color_prev_nodes = [n for n in prev_level_nodes if self.nodes_df[self.nodes_df['node_id'] == n]['color'].iloc[0] == node_color]

                    for prev_node in same_color_prev_nodes:
                        prev_node_font_size = self.nodes_df[self.nodes_df['node_id'] == prev_node]['font_size'].iloc[0]
                        if abs(prev_node_font_size - node_font_size) <= self.font_threshold:
                            nodes_to_collapse.append(node)
                            break

                # If there are nodes to collapse, adjust them and mark the flag
                if nodes_to_collapse:
                    changed = True
                    for node in nodes_to_collapse:
                        self.hierarchy[node] = level - 1

                    # Adjust levels of subsequent nodes
                    for node, lvl in self.hierarchy.items():
                        if lvl > level:
                            self.hierarchy[node] = lvl - 1
        return self.hierarchy
    
        
    def _detect_root_nodes(self):
        """
        Detects root nodes based on font size and non-white pixel ratio.

        Returns:
        list: A list of root node IDs.
        """
        
        font_sizes = self.nodes_df['font_size'].tolist()
        bounding_boxes = self._extract_bounding_boxes(self.nodes_df)
        ratios = self._compute_non_white_pixel_ratio(bounding_boxes)
        self.nodes_df['Non_White_Ratio'] = ratios# assign the ratios to the nodes in the graph

        # Case 1: All nodes are similar in both font size and non-white ratio.
        if self.all_similar(font_sizes, self.font_threshold) and self.all_similar(ratios, self.ratio_threshold):
            # logger.info("all similar")
            for node_id in self.nodes_df['node_id']:
                self.hierarchy[node_id] = 0
            return self.hierarchy
        root_nodes = []
        max_font_size = max(self.nodes_df['font_size']) # a df
        for node_id, ratio in zip(self.nodes_df["node_id"], ratios):
            if ratio > 0.96 and not self.all_similar(ratios, self.ratio_threshold):
                self.hierarchy[node_id] = 1
                root_nodes.append(node_id)

        qualified_root_nodes = []
        for node_id in root_nodes:
            node_font_size = self.nodes_df.loc[self.nodes_df['node_id'] == node_id, 'font_size'].iloc[0]
            if (max_font_size - node_font_size) / max_font_size <= 0.15:
                qualified_root_nodes.append(node_id)
            else:
                self.hierarchy[node_id] = -1
                
        # Check if there are multiple nodes with the max font size
        max_font_size_nodes = self.nodes_df[self.nodes_df['font_size'] == max_font_size]['node_id'].tolist()
        if len(max_font_size_nodes) > 2:
            # Keep only the nodes with the largest font size
            root_nodes = max_font_size_nodes
        else:
            # Keep the qualified root nodes
            root_nodes = qualified_root_nodes 
        if not root_nodes:
          # If there are already root nodes, skip the next steps
            if self.all_similar(font_sizes, self.font_threshold):  # If font sizes are similar, use the non-white ratios.
                max_ratio = max(ratios)
                root_nodes = [node_id for node_id, ratio in zip(self.nodes_df["node_id"], ratios) if (max_ratio - ratio)  < self.ratio_threshold]
            else:  

                nodes_font_size_list = self.nodes_df["font_size"].tolist()
                max_font_size = max(nodes_font_size_list)
                # print("all weighted_scores:",weighted_scores)
                root_nodes = self.nodes_df.loc[(max_font_size - self.nodes_df['font_size']) / max_font_size < self.score_threshold, 'node_id'].tolist()
        
        for root_node in root_nodes:
            if self.hierarchy[root_node] != 1:  # Prevents overwriting nodes already set to level 1
                self.hierarchy[root_node] = 1
        return root_nodes
    
    def _detect_all_nodes_hierarchy(self,root_nodes):
        """
        Detects the hierarchy of all nodes in the mind map starting from the root nodes.

        Parameters:
        root_nodes (list): A list of root node IDs.

        Returns:
        dict: A dictionary mapping node IDs to their hierarchical level.
        """
        # when using old way to detect root nodes
        # root_nodes = self._detect_root_nodes() 
        adjacency = defaultdict(list)
        for index, row in self.connections_df.iterrows():
            adjacency[row['node_a']].append(row['node_b'])
            adjacency[row['node_b']].append(row['node_a'])
        
        visited = set()
        queue = [(root_node, 1) for root_node in root_nodes]

        while queue:
            current_node, level = queue.pop(0)
            visited.add(current_node)

            for neighbor in adjacency[current_node]:
                if neighbor not in visited:
                    if self.hierarchy[neighbor] == -1 or self.hierarchy[neighbor] > level + 1:
                        self.hierarchy[neighbor] = level + 1
                        queue.append((neighbor, level + 1))
        # print("check hieararchy:", hierarchy)
        # Step 4: Set disconnected nodes
        for node_id, level in self.hierarchy.items():
            if level == -1:
                self.hierarchy[node_id] = 0

        self.hierarchy = self.adjust_node_levels()

        return self.hierarchy
    
    def _detect_root_nodes_with_gpt4(self):
        """
        Detects root nodes using GPT-4 and adjusts the hierarchy accordingly.

        Returns:
        list: A list of matched root node IDs based on GPT-4 analysis.
        """
        # Assumes there is a method self._detect_root_nodes() that returns root node IDs
        root_nodes_ids = self._detect_root_nodes()
        
        # Assumes there is a method detect_highest_hierarchy_nodes_with_gpt4() to integrate with GPT-4
        response = detect_highest_hierarchy_nodes_with_gpt4(self.file_name, self.bucket_name, self.openai_api_key)
        
        if response.get("highest_hierarchy_nodes") == "no":
            logger.info("The highest hierarchy nodes are hard to detect using GPT-4!")
            return root_nodes_ids
        
        # Get the highest hierarchy nodes from the GPT-4 response
        # if GPT-4 detected the root nodes we used fuzzy matching with the earlier root nodes detected
        highest_hierarchy_nodes_by_gpt4 = response.get("highest_hierarchy_nodes")
        
        # Create a mapping of node text to node ID
        node_id_text_mapping = {self.nodes_df[self.nodes_df['node_id'] == node_id]['text'].iloc[0]: node_id for node_id in root_nodes_ids}
        
        # Match GPT-4 nodes to node IDs using token sort ratio
        matched_nodes_ids = []
        for gpt_node in highest_hierarchy_nodes_by_gpt4:
            for node_text, node_id in node_id_text_mapping.items():
                cleaned_text = clean_node_text(node_text)
                if fuzz.token_sort_ratio(gpt_node, cleaned_text) >= 70:  # Threshold of 70
                    matched_nodes_ids.append(node_id)
        
        if matched_nodes_ids:
            # if theres matching then we need to reset the nodes hiearachy and assign hierarchy again
            self.hierarchy = {node_id: -1 for node_id in self.nodes_df['node_id']}
            for root_node in matched_nodes_ids:
                self.hierarchy[root_node] = 1
            return matched_nodes_ids
        else:
            return root_nodes_ids
    
    def process(self):
        """
        Processes the mind map to determine the hierarchy of nodes.

        Returns:
        dict: A dictionary mapping node IDs to their hierarchical level after processing.
        """
        root_nodes = self._detect_root_nodes_with_gpt4()
        
        self.hierarchy = self._detect_all_nodes_hierarchy(root_nodes)
        return self.hierarchy
    
# Function to clean up node text entries by removing drawing references
def clean_node_text(text):
    return re.sub(r'drawing_\d+', '', text).strip()