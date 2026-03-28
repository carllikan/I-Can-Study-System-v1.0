from google.cloud import firestore
from vertexai.preview.language_models import TextGenerationModel
# from vertexai.generative_models import GenerativeModel, Part, FinishReason
from vertexai.preview.generative_models import GenerativeModel
import vertexai.preview.generative_models as generative_models
from dotenv import load_dotenv
import os
import logging


from langchain.chat_models import ChatVertexAI
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
import vertexai
from vertexai.language_models import TextGenerationModel
from google.oauth2 import service_account
import json

load_dotenv()

class ContentbasePattern:


    def __init__(self):
        self.model = TextGenerationModel.from_pretrained("text-bison")
        self.db_firestore = firestore.Client(project=os.getenv("PROJECT"))
        self.gemini_model = GenerativeModel("gemini-1.0-pro-001")

    def _predict(self, prompt):
        '''
        Generates a prediction using the text generation model.

        Parameters:
        - prompt (str): The input prompt.

        Returns:
        - str: The generated prediction.
        '''
        parameters = {
            "max_output_tokens": 1024,
            "temperature": 0,
            "top_p": 0.8,
            "top_k": 40
        }
        response = self.model.predict(prompt, **parameters)
        return response.text
    

    def generate(self, prompt):
        # model = GenerativeModel("gemini-1.0-pro-001")
        generation_config = {
            "max_output_tokens": 2048,
            "temperature": 0.0,
            "top_p": 1,
        }

        safety_settings = {
        generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        responses = self.gemini_model.generate_content(
            [prompt],
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False,
        )




        return responses.text
        
        
    def load_negative_pattern_template(self, code):
        '''
        Loads a negative pattern template from Firestore.

        Parameters:
        - code (str): The pattern code.

        Returns:
        - tuple: A tuple containing negative indicators and negative template.
        '''
        pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
        pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        docs = pattern_query.stream()
        doc = next(docs)
        negative_indicators = doc.to_dict().get('negative_indicators')
        
        template_collection = self.db_firestore.collection('reflection_template_collection')
        negative_template_query = template_collection.document('negative_indicator_prompt_v_1').get()
        template_data = negative_template_query.to_dict()

        negative_template = template_data.get('prompt')



        
        return negative_indicators, negative_template
    
    def load_positive_pattern_template(self, code):
        '''
        Loads a positive pattern template from Firestore.

        Parameters:
        - code (str): The pattern code.

        Returns:
        - tuple: A tuple containing positive indicators and positive template.
        '''
        pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
        pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        docs = pattern_query.stream()
        doc = next(docs)
        positive_indicators = doc.to_dict().get('positive_indicators')
        
        template_collection = self.db_firestore.collection('reflection_template_collection')
        positive_template_query = template_collection.document('positive_indicator_prompt_v_1').get()
        template_data = positive_template_query.to_dict()

        positive_template = template_data.get('prompt')



        
        return positive_indicators, positive_template
    
    def _extract_json_from_response(self, response):
        '''
        Extracts JSON data from a response.

        Parameters:
        - response (str): The response containing JSON data.

        Returns:
        - dict: The extracted JSON data.
        '''
        start_index = response.find('{')
        end_index = response.rfind('}') + 1
        json_str = response[start_index:end_index]
        
        return json.loads(json_str)

    def _extract_indicators(self, data):
        '''
        Extracts indicators from JSON data.

        Parameters:
        - data (dict): JSON data containing indicators.

        Returns:
        - dict: Extracted indicators.
        '''
        result = {}
        for entry in data["indicators"]:
            for key, value in entry.items():
                if "indicator" in key and value == "yes":
                    result[key] = {"evidence": entry["evidence"]}
        return result

    def _get_score(self, indicators, result):
        '''
        Calculates the score based on indicators and results.

        Parameters:
        - indicators (list): List of indicators.
        - result (dict): Result dictionary.

        Returns:
        - int: The calculated score.
        '''
        score_dict = {}
        for indicator in indicators:
            for key, value in indicator.items():
                indicator_num = int(key.split('_')[-1])
                score_dict[f'indicator_{indicator_num}'] = value['score']

        return sum(score_dict[ind] for ind in result if ind in score_dict)

    def analyze(self,positive_prompt, negative_prompt,code):
        '''
        Analyzes patterns using positive and negative prompts.

        Parameters:
        - positive_prompt (str): The positive prompt.
        - negative_prompt (str): The negative prompt.
        - code (str): The pattern code.

        Returns:
        - tuple: A tuple containing final score, positive result, negative result, positive data, and negative data.
        '''
        
        # logging.info(f"positive_prompt: {positive_prompt}")
        # logging.info(f"negative_prompt: {negative_prompt}")

        # positive_res = self._predict(positive_prompt)
        # negative_res = self._predict(negative_prompt)
        positive_res = self.generate(positive_prompt)
        negative_res = self.generate(negative_prompt)
        # logging.info(f"positive_res: {positive_res}")
        # logging.info(f"negative_res: {negative_res}")
        # print(positive_res)
        # print(negative_res)

        pos_data = self._extract_json_from_response(positive_res)
        logging.info(f"pos_data: {pos_data}")
        print(pos_data)
        neg_data = self._extract_json_from_response(negative_res)


        result_pos = self._extract_indicators(pos_data)

        result_neg = self._extract_indicators(neg_data)
        # logging.info(f"result_pos: {result_pos}")
        # logging.info(f"result_neg: {result_neg}")
        # print(result_pos)
        # print(result_neg)
 
        pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
        pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        docs = pattern_query.stream()
        doc = next(docs)
        negative_indicators = doc.to_dict().get('negative_indicators')
        total_neg_score = self._get_score(negative_indicators, result_neg)
        

        positive_indicators = doc.to_dict().get('positive_indicators')
        total_pos_score = self._get_score(positive_indicators, result_pos)
        # logging.info(f"total_neg_score: {total_neg_score}")
        # print(total_neg_score)
        # logging.info(f"total_pos_score: {total_pos_score}")
        # print(total_pos_score)


        # total_pos_score = self._get_score(data["patterns"][pattern_index]["positive_indicators"], result_pos)
        # total_neg_score = self._get_score(data["patterns"][pattern_index]["negative_indicators"], result_neg)

        final_score = total_pos_score - total_neg_score

        for indicator in pos_data.get("indicators", []):
            if "indicator_0" in indicator and indicator["indicator_0"] == "no":
                final_score = final_score - 100

        return final_score, result_pos,result_neg,pos_data,neg_data
    
    def load_pattern_template(self, code):
        '''
        Loads a pattern template from Firestore.

        Parameters:
        - code (str): The pattern code.

        Returns:
        - tuple: A tuple containing pattern and template.
        '''
        pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
        pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
        template_collection = self.db_firestore.collection('reflection_template_collection')
        template_query = template_collection.order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        pattern = {}
        template = {}
        for p in pattern_query.stream():
            pattern = p.to_dict()
        for t in template_query.stream():
            template = t.to_dict()

        return pattern, template
    
    def process_pattern(self, pattern_code, **kwargs):
        '''
        Processes a pattern based on the provided code and keyword arguments.

        Parameters:
        - pattern_code (str): The pattern code.
        - kwargs (dict): Keyword arguments for text sections.

        Returns:
        - dict: The processed pattern result.
        '''
        pattern, template = self.load_pattern_template(pattern_code)
        if pattern == {} or template == {}:
            return "The pattern or template is not ready"
        
        # Safely get the values from kwargs
        experience = kwargs.get('experience', '')
        reflection = kwargs.get('reflection', '')
        abstraction = kwargs.get('abstraction', '')
        experimentation = kwargs.get('experimentation', '')
        
        # Dynamically invoke the method based on the pattern_code
        result = self.generate_output(pattern, pattern_code, experience = experience, reflection = reflection, abstraction = abstraction, experimentation = experimentation)
        return result
    
    def generate_output(self, pattern, pattern_code,  **kwargs):
        '''
        Generates output based on a pattern and template.

        Parameters:
        - pattern (dict): The pattern dictionary.
        - pattern_code (str): The pattern code.
        - kwargs (dict): Keyword arguments for text sections.

        Returns:
        - dict: The generated output.
        '''
        relevant_sections_list = pattern['relevant_sections']
        text_for_evaluation = ""
        for section_name, section_value in kwargs.items():
            if section_name in relevant_sections_list:
                text_for_evaluation += f"{section_name}:{section_value}"
                text_for_evaluation += " " + "\n"

        negative_indicators, negative_template = self.load_negative_pattern_template(pattern_code)
        positive_indicators, positive_template = self.load_positive_pattern_template(pattern_code)        
        negative_prompt = negative_template.format(negative_indicators=negative_indicators, text_evaluation=text_for_evaluation)
        positive_prompt = positive_template.format(positive_indicators=positive_indicators, text_evaluation=text_for_evaluation)
        final_score, result_pos, result_neg,pos_data,neg_data = self.analyze(positive_prompt, negative_prompt, pattern_code)

        Is_pattern_exist, evidences_pos, evidences_neg = ContentbasePattern.get_evidence(final_score, result_pos,result_neg)
        evidence_dict = {
        "is_pattern_exist": Is_pattern_exist,
        "positive_evidences": evidences_pos,
        "negative_evidences": evidences_neg,
        "final_score": final_score,
        "positive_response": pos_data,
        "negative_response": neg_data,
        "positive_indicators": positive_indicators,
        "negative_indicators": negative_indicators
    }

        return evidence_dict

    @staticmethod
    def get_evidence(final_score, result_pos,result_neg):
        '''
        Retrieves evidence based on final score and results.

        Parameters:
        - final_score (int): The final score.
        - result_pos (dict): Positive results.
        - result_neg (dict): Negative results.

        Returns:
        - tuple: A tuple containing pattern existence, positive evidence, and negative evidence.
        '''
        evidences_pos = []
        evidences_neg = []
        Is_pattern_exist = ""
        if final_score > 0:
            for i, (key, value) in enumerate(result_pos.items()):
                evidences_pos.append(f"{i+1}. {value['evidence']}")
            Is_pattern_exist = "Pattern exist"
        if final_score <= 0:
            for i, (key, value) in enumerate(result_neg.items()):
                evidences_neg.append(f"{i+1}. {value['evidence']}")
            Is_pattern_exist = "Pattern does not exist"
        return Is_pattern_exist, evidences_pos, evidences_neg
    
    def get_patternMap(self):
        '''
        Retrieves the pattern map from Firestore.

        Returns:
        - dict: The pattern map.
        '''
        pattern_map_doc=self.db_firestore.collection("reflection_pattern_map").document("pattern_map").get()

        if pattern_map_doc.exists:
            # Get the data from the document
            loaded_pattern_map = pattern_map_doc.to_dict()
            return loaded_pattern_map
        else:
            print("Document does not exist")


    def get_field(self):
        '''
        Retrieves reflection fields and data from Firestore.

        Returns:
        - tuple: A tuple containing reflection fields list and data dictionary.
        '''
        doc =self.db_firestore.collection("reflection_fields").document("fields_v1").get()

        if doc.exists:
            # Get the data from the document
            data = doc.to_dict()

            reflection_fields = []

            # Loop through each category (experience, reflection, abstraction) and add their fields to the list
            for category_fields in data.values():
                reflection_fields.extend(category_fields)

            # Separate the field names into their respective categories

            return reflection_fields,data
        else:
            print("Document does not exist")
    








