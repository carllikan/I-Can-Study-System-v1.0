from google.cloud import firestore
from vertexai.preview.language_models import TextGenerationModel
from dotenv import load_dotenv
import json
import re
import logging
import os
from langchain.chat_models import ChatVertexAI
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from vertexai.language_models import ChatModel, \
                                     InputOutputTextPair
load_dotenv()
class ReflectivePattern:

    def __init__(self):
        self.chat_model = ChatModel.from_pretrained("chat-bison@001")
        
        self.db_firestore = firestore.Client(project=os.getenv("PROJECT"))
    
    def _predict(self, context,examples,prompt):
        '''
        Generates a prediction using the chat model.

        Parameters:
        - context (str): The context for the chat model.
        - examples (list): A list of InputOutputTextPair objects.
        - prompt (str): The prompt for the chat model.

        Returns:
        - str: The generated prediction.
        '''
        parameters = {
            "max_output_tokens": 1024,
            "temperature": 0,
            "top_p": 0.8,
            "top_k": 40
        }
        chat = self.chat_model.start_chat(context=context, examples=examples, **parameters)
        response = chat.send_message(prompt)
        return response.text

        
    # def load_BRN_pattern_template(self, code):
    #     '''
    #     Loads a BRN pattern template from Firestore.

    #     Parameters:
    #     - code (str): The pattern code.

    #     Returns:
    #     - dict: The loaded pattern and template.
    #     '''
    #     pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
    #     pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
    #     template_collection = self.db_firestore.collection('reflection_template_collection')
    #     template_query = template_collection.document('reflectiveTechnique_BRN_prompt_v_1').get()
    #     pattern = {}
    #     if template_query.exists:
    #         template = template_query.to_dict()
    #     else:
    #         template = {}

    #     for p in pattern_query.stream():
    #         pattern = p.to_dict()
    #     return pattern, template

    # def load_OAE_pattern_template(self, code):
    #     '''
    #     Loads an OAE pattern template from Firestore.

    #     Parameters:
    #     - code (str): The pattern code.

    #     Returns:
    #     - dict: The loaded pattern and template.
    #     '''
    #     pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
    #     pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
    #     template_collection = self.db_firestore.collection('reflection_template_collection')
    #     template_query = template_collection.document('reflectiveTechnique_OAE_prompt_v_1').get()
    #     pattern = {}
    #     if template_query.exists:
    #         template = template_query.to_dict()
    #     else:
    #         template = {}

    #     for p in pattern_query.stream():
    #         pattern = p.to_dict()
        
    #     return pattern, template
    
    # def load_SRF_pattern_template(self, code):
    #     '''
    #     Loads an SRF pattern template from Firestore.

    #     Parameters:
    #     - code (str): The pattern code.

    #     Returns:
    #     - dict: The loaded pattern and template.
    #     '''
    #     pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
    #     pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
    #     template_collection = self.db_firestore.collection('reflection_template_collection')
    #     template_query = template_collection.document('reflectiveTechnique_SRF_prompt_v_1').get()
    #     pattern = {}
    #     if template_query.exists:
    #         template = template_query.to_dict()
    #     else:
    #         template = {}

    #     for p in pattern_query.stream():
    #         pattern = p.to_dict()
        
    #     return pattern, template
    
    # def load_TAN_pattern_template(self, code):
    #     '''
    #     Loads a TAN pattern template from Firestore.

    #     Parameters:
    #     - code (str): The pattern code.

    #     Returns:
    #     - dict: The loaded pattern and template.
    #     '''
    #     pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
    #     pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
    #     template_collection = self.db_firestore.collection('reflection_template_collection')
    #     template_query = template_collection.document('reflectiveTechnique_TAN_prompt_v_1').get()
    #     pattern = {}
    #     if template_query.exists:
    #         template = template_query.to_dict()
    #     else:
    #         template = {}

    #     for p in pattern_query.stream():
    #         pattern = p.to_dict()
        
    #     return pattern, template
    def fix_quotes(self, text):
        '''
        Fixes quotes in the given text.

        Parameters:
        - text (str): The text to fix.

        Returns:
        - str: The text with fixed quotes.
        '''
        # 
        text = text.replace('“', '"').replace('”', '"')
        return text
    # def load_REN_pattern_template(self, code):
    #     '''
    #     Loads a REN pattern template from Firestore.

    #     Parameters:
    #     - code (str): The pattern code.

    #     Returns:
    #     - dict: The loaded pattern and template.
    #     '''
    #     pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
    #     pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
    #     template_collection = self.db_firestore.collection('reflection_template_collection')
    #     template_query = template_collection.document('reflectiveTechnique_REN_prompt_v_1').get()
    #     pattern = {}
    #     if template_query.exists:
    #         template = template_query.to_dict()
    #     else:
    #         template = {}

    #     for p in pattern_query.stream():
    #         pattern = p.to_dict()
        
    #     return pattern, template
    
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
        # logging.info(f"JSON string: {json_str}")
        return json.loads(json_str)
    
    def generate_output(self, pattern, template, **kwargs):
        '''
        Generates output based on a pattern and template.

        Parameters:
        - pattern (dict): The pattern dictionary.
        - template (dict): The template dictionary.
        - kwargs (dict): Keyword arguments for text sections.

        Returns:
        - dict: The generated output.
        '''
        prompt_str = template['prompt']
        pattern_name_str = pattern['pattern_name']
        pattern_description_str = pattern['pattern_description']
        example_list = pattern['examples']
        relevant_sections_list = pattern['relevant_sections']

        pattern_context = pattern['context']

        text_for_evaluation = ""
        for section_name, section_value in kwargs.items():
            if section_name in relevant_sections_list:
                text_for_evaluation += f"{section_name}:{section_value}"
                text_for_evaluation += " " + "\n"
        final_prompt = prompt_str.format(text_evaluation = text_for_evaluation)
        examples = []
        for item in example_list:
            pair = InputOutputTextPair(
                input_text=item["text"],
                output_text=item["rationale"]
            )
            examples.append(pair)

        res = self._predict( pattern_context,examples,final_prompt)
        # logging.info(f"res: {res}")

        res_json = self.process_response(res)
        # logging.info(f"res_json: {res_json}")
        fixed_text = self.fix_quotes(res_json)
        # logging.info(f"fixed_text: {fixed_text}")
        # clean_text = self.clean_nested_quotes(fixed_text)
        # logging.info(f"clean_text: {clean_text}")
        scale, explanation = self.extract_variables(fixed_text)
        if scale is None and explanation is None:
            scale = "Strong"
            explanation = "This pattern does not exist"


        res_dict = {
        "scale": scale,
        "explanation": explanation
        }


        return res_dict
    # def clean_nested_quotes(self, text):
    #     nested_quotes_pattern = r'("[^"\\]*(?:\\.[^"\\]*)*")'

    #     def replace_nested_quotes(match):
    #         return match.group(0).replace('"', '', 1).rsplit('"', 1)[0]

    #     # 
    #     cleaned_text = re.sub(nested_quotes_pattern, replace_nested_quotes, text)
    #     return cleaned_text
    def extract_variables(self, text):
        cleaned_text = text.replace('\n', '\\n').replace('\t', '\\t')
        
        # logging.info(f"scaletext: {cleaned_text}")
        try:
            data = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None, None

        scale = data.get("scale", None)
        explanation = data.get("Explanation", None)
        return scale, explanation
        
    def process_response(self, res):
        '''
        Processes the response and extracts scale and explanation.

        Parameters:
        - res (str): The response to process.

        Returns:
        - str: The processed response.
        '''
        try:
            data = self._extract_json_from_response(res)

            if data.get("scale") == "Strong":
                return "pattern does not exist"
            else:
                return data.get("Explanation", "")  
        except json.JSONDecodeError:
            return res
    def load_pattern_template(self, code):
        '''
        Loads a pattern template from Firestore based on the provided code.

        Parameters:
        - code (str): The pattern code.

        Returns:
        - dict: The loaded pattern and template.
        '''
        # Common collection for patterns
        pattern_collection = self.db_firestore.collection('reflection_pattern_collection')
        pattern_query = pattern_collection.where("pattern_code", "==", code).order_by("version", direction=firestore.Query.DESCENDING).limit(1)
        
        # Dynamically build the document ID for the template based on the code
        template_id = f'reflectiveTechnique_{code}_prompt_v_1'
        template_collection = self.db_firestore.collection('reflection_template_collection')
        template_query = template_collection.document(template_id).get()
        
        pattern = {}
        if template_query.exists:
            template = template_query.to_dict()
        else:
            template = {}

        for p in pattern_query.stream():
            pattern = p.to_dict()
        
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
        # Load the pattern and template using the new consolidated function
        pattern, template = self.load_pattern_template(pattern_code)
        if pattern == {} or template == {}:
            return "The pattern or template is not ready"
        
        # Safely get the values from kwargs
        experience = "Experience start:\n " + kwargs.get('experience', '') + "\n experience end "
        reflection = "reflection start:\n " + kwargs.get('reflection', '') + "\n reflection end "
        abstraction = "abstraction start:\n " + kwargs.get('abstraction', '') + "\n abstraction end "
        experimentation = "experimentation start:\n " + kwargs.get('experimentation', '') + "\n experimentation end "
        
        # Dynamically invoke the method based on the pattern_code
        result = self.generate_output(pattern, template, experience=experience, reflection=reflection, abstraction=abstraction, experimentation=experimentation)
        return result


    # def process_pattern(self, pattern_code, **kwargs):
    #     '''
    #     Processes a pattern based on the provided code and keyword arguments.

    #     Parameters:
    #     - pattern_code (str): The pattern code.
    #     - kwargs (dict): Keyword arguments for text sections.

    #     Returns:
    #     - dict: The processed pattern result.
    #     '''
    #     if pattern_code == "BRN":
    #         pattern, template = self.load_BRN_pattern_template(pattern_code)
    #     elif pattern_code == "OAE":
    #         pattern, template = self.load_OAE_pattern_template(pattern_code)
    #     elif pattern_code == "SRF":
    #         pattern, template = self.load_SRF_pattern_template(pattern_code)
    #     elif pattern_code == "TAN":
    #         pattern, template = self.load_TAN_pattern_template(pattern_code)
    #     elif pattern_code == "REN":
    #         pattern, template = self.load_REN_pattern_template(pattern_code)
    #     else:
    #         return "Invalid pattern code"
    #     if pattern == {} or template == {}:
    #         return "The pattern or template is not ready"
        
    #     # Safely get the values from kwargs
    #     experience = "Experience start:\n " + kwargs.get('experience', '') + "\n experience end "
    #     reflection = "reflection start:\n " + kwargs.get('reflection', '') + "\n reflection end "
    #     abstraction = "abstraction start:\n " + kwargs.get('abstraction', '') + "\n abstraction end "
    #     experimentation = "experimentation start:\n " + kwargs.get('experimentation', '') + "\n experimentation end "
        
    #     # Dynamically invoke the method based on the pattern_code
    #     result = self.generate_output(pattern, template, experience = experience, reflection = reflection, abstraction = abstraction, experimentation = experimentation)
    #     return result
    
    # def load_langchain_template(self):
    #     doc_data = self.db_firestore.collection("reflection_Langchain_template").document("template_v1").get().to_dict()
    #     pattern_prompt_template = doc_data.get('pattern_prompt_template')
    #     example_output_template = doc_data.get('example_output_template')
    #     text_evaluation_template = doc_data.get('text_evaluation_template')
        
    #     return pattern_prompt_template,example_output_template,text_evaluation_template
    
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
        - tuple: A tuple containing reflection_fields list and data dictionary.
        '''
        doc =self.db_firestore.collection("reflection_fields").document("fields_v1").get()

        if doc.exists:
            # Get the data from the document
            data = doc.to_dict()
            reflection_fields = []
            # Loop through each category (experience, reflection, abstraction) and add their fields to the list
            for category_fields in data.values():
                reflection_fields.extend(category_fields)
            return reflection_fields,data
        else:
            print("Document does not exist")