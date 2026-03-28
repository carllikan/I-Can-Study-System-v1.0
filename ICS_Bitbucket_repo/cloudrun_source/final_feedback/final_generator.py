import logging 

class FINALGenerator:
    def __init__(self):
        self.final_ans = {"feedback": "general_feedback", "principles": {}, "patterns":{}}
        self.reflection_exist = False
        self.mindmap_exist = False
        self.principle_collection = {}
        self.pattern_id_name_map = {}
        self.principle_map = {}
        self.pending_feedback = {}
        self.pending_weight_matrix = {}
        self.pattern_name_id_map = {}
        self.levels = ["level_1", "level_2", "level_3", "level_4"]

        self.ref_pattern_id_list = []
        self.mm_pattern_id_dict = {}

    def _update_firestore_data(self, db_firestore, request_json):
        self.principle_collection = db_firestore.collection('principle_collection'). \
            document('collection').get().to_dict()
        self.pattern_id_name_map = db_firestore.collection('pattern_id_name_map'). \
            document('mapping').get().to_dict()
        self.pattern_name_id_map = {v: k for k, v in self.pattern_id_name_map.items()}
        self.principle_map = db_firestore.collection('principle_stage_map'). \
            document('v1').get().to_dict()
        self.pending_feedback = db_firestore.collection('final_feedback'). \
            document(request_json['mainjob-ID']).get().to_dict()
        self.pending_weight_matrix = db_firestore.collection('ics_final_syntehsis_weight'). \
            document('weight_matrix').get().to_dict()

    def _check_components(self, request_json):
        logging.debug(self.pending_feedback)
        logging.debug(request_json['component_list'])
        logging.exception(self.pending_feedback)
        if all(component in self.pending_feedback for component in request_json['component_list']):
            return True

    def _get_principles(self, request_json):
        request_type = self.pending_feedback["request_type"]
        standard_user_stage = self.pending_feedback["user_stage"]
        stage_map = {
            "st-rapid-start": "RS",
            "st-fundamentals": "F1",
            "st-fundamentals-2": "F2",
            "st-briefing": "BR",
            "st-technique-training": "TT"
        }   
        user_stage = stage_map[standard_user_stage]
        reflection_principles = []
        mindmap_principles = []
        if "KOLBS" in self.pending_feedback:
            self.reflection_exist = True
            reflection_principles = self.principle_map["reflection"][request_type][user_stage]
            reflection_evaluation = self.pending_feedback["KOLBS"]["feedback"]

            for ref_name, ref_feedback in reflection_evaluation.items():
                pattern_id = self.pattern_id_name_map[ref_name.lower()]
                self.ref_pattern_id_list.append((pattern_id, ref_feedback))

        fixed_keys = ["KOLBS", "user_id", "user_stage", "request_type"]

        if any(key not in fixed_keys for key in self.pending_feedback):
            mindmap_principles = self.principle_map["mindmap"][request_type][user_stage]
            self.mindmap_exist = True
            for component in request_json["component_list"]:
                self.mm_pattern_id_dict[component] = []
                if component.upper() == "KOLBS":
                    continue
                # Check whether the mindmap file is processed correctly
                if "error_message" not in self.pending_feedback[component]:
                    mindmap_evaluation = self.pending_feedback[component]["evaluation"]
                    # Record pattern feedbacks(certainty, existence) in single image
                    for pattern_name, pattern_feedback in mindmap_evaluation.items():
                        pattern_id = self.pattern_id_name_map[pattern_name]
                        self.mm_pattern_id_dict[component].append((pattern_id, pattern_feedback))

        principles = list(set(reflection_principles + mindmap_principles))
        return self._generate_answer(principles)

    def _generate_answer(self, principles):
        for principle in principles:
            principle_details = self.principle_collection[principle]
            for level in self.levels:
                # Omit the the principle level without any patterns
                if "patterns" not in principle_details[level]:
                    continue
                applicability = 0
                self.final_ans["principles"][f"{principle}_{level}"] = \
                    {"principle_name": principle_details["name"], "principle_level": level,
                        "principle_applicability": "0%", "principle_level_feedback":
                            principle_details[level]["symptom"],}
                
                
                # Check whether current principle contains mindmap patterns
                mm_pattern_in_principle = "mindmap" in principle_details[level]["patterns"]
                # Check whether current principle contains reflection patterns
                ref_pattern_in_principle = "reflection" in principle_details[level]["patterns"]

                applicability += self._mindmap_answer(applicability,
                                                     mm_pattern_in_principle, principle, principle_details, level)

                applicability += self._reflection_answer(applicability, ref_pattern_in_principle, principle,
                                                        principle_details, level)

                if applicability == 0:
                    self.final_ans["principles"].pop(f"{principle}_{level}")
                else:
                    applicability = str(applicability * 100) + '%'
                    self.final_ans["principles"][f"{principle}_{level}"]["principle_applicability"] = str(applicability)

        return self.final_ans

    def _mindmap_answer(self, applicability, mm_pattern_in_principle, principle, principle_details, level):
        if not self.mindmap_exist or not mm_pattern_in_principle:
            return 0
        for _, pattern_list in self.mm_pattern_id_dict.items():
            for pattern in pattern_list:
                pattern_id = pattern[0]
                pattern_feedback = pattern[1]
                # Check whether the mind map pattern is in the current principle level, and whether it has a weight
                applicability = self._update_answer(applicability,
                                                    principle, principle_details, level, pattern_id,
                                                    pattern_feedback, "mindmap")
        return applicability

    def _reflection_answer(self, applicability, ref_pattern_in_principle, principle, principle_details, level):
        if not self.reflection_exist or not ref_pattern_in_principle:
            return 0
        
        for pattern in self.ref_pattern_id_list:
            pattern_id = pattern[0]
            pattern_feedback = pattern[1]
            # Check whether the reflection pattern is in the current principle level, and whether it has a weight
            applicability = self._update_answer(applicability,
                                                principle, principle_details, level, pattern_id, pattern_feedback,
                                                "reflection")
        return applicability

    def _update_answer(self, applicability, principle, principle_details, level, pattern_id, pattern_feedback, type):
        if type == "mindmap":
            pattern_exist = pattern_feedback["pattern_existence"] == True
            if pattern_id not in principle_details[level]["patterns"]["mindmap"]:
                return applicability
            # or principle not in self.pending_weight_matrix[self.pending_feedback["user_stage"]] or\
            #     (principle in self.pending_weight_matrix[self.pending_feedback["user_stage"]] and level not in self.pending_weight_matrix[self.pending_feedback["user_stage"]][principle])
        else:
            pattern_exist = False
            if "is_pattern_exist" in pattern_feedback:
                pattern_exist = pattern_feedback["is_pattern_exist"] == "Pattern exist"
            if pattern_id not in principle_details[level]["patterns"]["reflection"]:
                return applicability

        # if type == "mindmap":
        #     pattern_exist = pattern_feedback["pattern_existence"] == True

        # else:
        #     pattern_exist = False
        #     if "is_pattern_exist" in pattern_feedback:
        #         pattern_exist = pattern_feedback["is_pattern_exist"] == "Pattern exist"

        if pattern_exist:
            if principle in self.pending_weight_matrix and level in self.pending_weight_matrix[principle] and pattern_id in self.pending_weight_matrix[principle][level]:
                weight = self.pending_weight_matrix[principle][level][pattern_id]
            else:
                weight = 0.1
            applicability += weight
            principle_name = principle_details["name"]
            if f"{principle}_{level}" not in self.final_ans["principles"]:

                self.final_ans["principles"][f"{principle}_{level}"] = \
                    {"principle_name": principle_name, "principle_level": level,
                        "principle_applicability": "0%", "principle_level_feedback":
                            principle_details[level]["symptom"]}
                self.final_ans["patterns"][pattern_id] = \
                    {"pattern_name": self.pattern_name_id_map[pattern_id], "pattern_feedback": pattern_feedback}


            else:
                self.final_ans["patterns"][pattern_id] = \
                    {"pattern_name": self.pattern_name_id_map[pattern_id], "pattern_feedback": pattern_feedback}

        return applicability