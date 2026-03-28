from flask import Flask, request, jsonify, Response
from flask_utils import apply_security_headers
import os
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
import logging 
from google.cloud import firestore
import pytz
from sql_orm import *
from std_response import *
load_dotenv()
logger = logging.getLogger()
app = Flask(__name__)
app.after_request(apply_security_headers)

@app.route('/', methods = ['POST'])
def main():
    if request.method == 'POST':
        aest = pytz.timezone('Australia/Sydney')
        PROJECT = os.getenv("PROJECT")
        # Validate the request
        now = datetime.now(aest)
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")
        request_json = request.get_json(silent=True)
        logger.warning(request_json)
        required_fields = ['mainjob-ID', 'user_id', 'component_list']
        
        for field in required_fields:
            # check whether required fields in request
            if field not in request_json:
                return create_response(f'Request must contain {field}', 400, request.method)
            if request_json[field] == "":
                return create_response(f'{field} must not be empty', 400, request.method)

        db_firestore = firestore.Client(PROJECT)
        pending_feedback = db_firestore.collection('final_feedback').document(request_json['mainjob-ID']).get().to_dict()
        logger.warning(pending_feedback)
        pending_weight_matrix = db_firestore.collection('final_feedback').document('weight_matrix').get().to_dict()
        logger.warning(pending_weight_matrix)

        if all(component in pending_feedback for component in request_json['component_list']):
            engine = initial_engine()
            
            try:
                evalapi_update_query = {"job_id":request_json['mainjob-ID'],
                                        "end_timestamp":end_time}
                evalApiJobs_update(engine, evalapi_update_query)

            except Exception as e:
                logger.exception(e)
                return create_response("Unable to successfully Update Endtime of Main Eval!\
                                Please check the application logs for more details.", 500, request.method)            

            final_ans = {"feedback": "general_feedback", "principles": {}}
            reflection_exist = False
            mindmap_exist = False
            principle_collection = db_firestore.collection('principle_collection').document('collection').get().to_dict()
            pattern_id_name_map = db_firestore.collection('pattern_id_name_map').document('mapping').get().to_dict()
            pattern_name_id_map = {v: k for k, v in pattern_id_name_map.items()}
            levels = ["level_1", "level_2", "level_3", "level_4"]
            #stages = list(pending_weight_matrix.keys())
            #principles = list(set(sum([list(pending_weight_matrix[s].keys()) for s in stages],[])))
            principle_map = {
                "reflection": {
                    "enabling": {
                        "RS": ["BBE", "SDT", "FMT", "TMI", "TMS"],
                        "F1": ["DDY"],
                        "F2": ["HAH","ISG"],
                        "BF": ["BBE","KBO"],
                        "TT": []
                    },
                    "learning": {
                        "RS": ["BBE"],
                        "F1": ["DDY","HAH"],
                        "F2": ["HAH","ISG"],
                        "BF": ["BBE","KBO"],
                        "TT": ["HAH","RHL"]
                    }
                },
                "mindmap": {
                    "enabling": {
                        "RS": ["TMI"],
                        "F1": ["DDY"],
                        "F2": [],
                        "BF": [],
                        "TT": []
                    },
                    "learning": {
                        "RS": [],
                        "F1": ["HAH", "DDY"],
                        "F2": ["HAH", "ISG"],
                        "BF": [],
                        "TT": ["HAH", "RHL"]
                    }
                }
            }
            
            if "KOLBS" in pending_feedback:
                reflection_exist = True
                reflection_principles = principle_map["reflection"][pending_feedback["request_type"]][pending_feedback["user_stage"]]
                reflection_evaluation = pending_feedback["KOLBS"]["feedback"]
                ref_pattern_id_list = []
                for eval in reflection_evaluation:
                    pattern_id = pattern_id_name_map[list(eval.keys())[0].lower()]
                    ref_pattern_id_list.append((pattern_id, eval[list(eval.keys())[0]]))

            fixed_keys = ["KOLBS", "user_id", "user_stage", "request_type"]
            for key in pending_feedback.keys():
                if key not in fixed_keys:
                    mindmap_principles =  principle_map["mindmap"][pending_feedback["request_type"]][pending_feedback["user_stage"]]
                    mindmap_exist = True
                    mm_pattern_id_dict = {}
                    mm_image_name_list = []
                    for component in request_json["component_list"]:
                        if component.upper() == "KOLBS":
                            continue
                        mm_image_name_list.append(component)
                        mindmap_evaluation = pending_feedback[component]["evaluation"]
                        for pattern_name, pattern_feedback in mindmap_evaluation.items():
                            pattern_id = pattern_id_name_map[pattern_name]
                            mm_pattern_id_dict[component] = []
                            mm_pattern_id_dict[component].append((pattern_id, pattern_feedback))

            principles = list(set((reflection_principles if reflection_exist else []) + (mindmap_principles if mindmap_exist else [])))
            
            for principle in principles:
                principle_details = principle_collection[principle]
                logger.info(principle_details)
                for level in levels:
                    applicability = 0
                    mm_pattern_in_principle = "patterns" in principle_details[level] and "mindmap" in principle_details[level]["patterns"]
                    ref_pattern_in_principle = "patterns" in principle_details[level] and "reflection" in principle_details[level]["patterns"]
                    if "patterns" not in principle_details[level]:
                        continue
                    
                    if mindmap_exist and mm_pattern_in_principle:
                        for pattern in mm_pattern_id_dict[mm_image_name_list[0]]:
                            pattern_id = pattern[0]
                            pattern_feedback = pattern[1]
                            if pattern_id in principle_details[level]["patterns"]["mindmap"] and pending_weight_matrix[pending_feedback["user_stage"]][principle][level]:
                                weight = pending_weight_matrix[pending_feedback["user_stage"]][principle][level][pattern_id]
                                applicability += weight
                                principle_name = principle_details["name"]
                                if f"{principle}_{level}" not in final_ans["principles"]:
                                    # final_ans["principles"] = {f"{principle}_{level}": {"principle_name": principle_name, "principle_level": level, 
                                    #                                                     "principle_applicability": "100%", "principle_level_feedback": principle_details[level]["symptom"],
                                    #                                                     "patterns": {}}}
                                    final_ans["principles"][f"{principle}_{level}"] = {"principle_name": principle_name, "principle_level": level, 
                                                                                        "principle_applicability": "0%", "principle_level_feedback": principle_details[level]["symptom"],
                                                                                        "patterns": {}}
                                    final_ans["principles"][f"{principle}_{level}"]["patterns"][pattern_id] = {"pattern_name": pattern_name_id_map[pattern_id], "pattern_certainty": "High", "pattern_feedback": pattern_feedback}

                                                                            
                                else:
                                    final_ans["principles"][f"{principle}_{level}"]["patterns"][pattern_id] = {"pattern_name": pattern_name_id_map[pattern_id], "pattern_certainty": "High", "pattern_feedback": pattern_feedback}
                    
                    if reflection_exist and ref_pattern_in_principle:
                        for pattern in ref_pattern_id_list:
                            pattern_id = pattern[0]
                            pattern_feedback = pattern[1]
                            if pattern_id in principle_details[level]["patterns"]["reflection"] and pending_weight_matrix[pending_feedback["user_stage"]][principle][level]:
                                weight = pending_weight_matrix[pending_feedback["user_stage"]][principle][level][pattern_id]
                                applicability += weight
                                principle_name = principle_details["name"]
                                if f"{principle}_{level}" not in final_ans["principles"]:
                                    # final_ans["principles"] = {f"{principle}_{level}": {"principle_name": principle_name, "principle_level": level, 
                                    #                                                     "principle_applicability": "100%", "principle_level_feedback": principle_details[level]["symptom"],
                                    #                                                     "patterns": {}}}
                                    final_ans["principles"][f"{principle}_{level}"] = {"principle_name": principle_name, "principle_level": level, 
                                                                                        "principle_applicability": "0%", "principle_level_feedback": principle_details[level]["symptom"],
                                                                                        "patterns": {}}
                                    final_ans["principles"][f"{principle}_{level}"]["patterns"][pattern_id] = {"pattern_name": pattern_name_id_map[pattern_id], "pattern_certainty": "High", "pattern_feedback": pattern_feedback}

                                                                            
                                else:
                                    final_ans["principles"][f"{principle}_{level}"]["patterns"][pattern_id] = {"pattern_name": pattern_name_id_map[pattern_id], "pattern_certainty": "High", "pattern_feedback": pattern_feedback}
                    applicability = str(applicability*100) + '%'
                    final_ans["principles"][f"{principle}_{level}"]["principle_applicability"] = str(applicability)
           
            db_firestore.collection("pending_feedback").document(request_json['mainjob-ID']).set(final_ans, merge=True)
            callback(request_json['mainjob-ID'], request_json['user_id'], final_ans)
            return create_response('Feedback is complete and returnning to Expert AI Endpoint', 200, request.method)

        return create_response('Feedback is still pending', 200, request.method)

    else:
        return create_response('Please use POST to request the API', 405, request.method)


def is_valid_input(value):
    # This pattern ensures the value contains characters typically allowed in URLs and text.
    # Alphanumeric characters, hyphens, underscores, periods, and tildes are considered valid.
    pattern = re.compile("^[a-zA-Z0-9-_.~]+$")
    return bool(pattern.match(value))


def callback(mainjob_id, user_id, feedback):
    payload = {
        "job_id" : mainjob_id,
        "user_id" : user_id,
        "feedback": feedback
    }
    headers = {
        'Content-Type': 'application/json',
    }
    final_url = os.getenv("CALLBACK_URL")
    try:
        response = requests.post(final_url, headers=headers, json=payload, timeout=200)
        logger.warning(response)
    except requests.exceptions.ReadTimeout: 
        pass
    return