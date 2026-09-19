import json

def select_failure(test_results: list) -> dict:
    """
    Selects the most useful/informative failing test case to investigate.
    Prioritizes duplicate issues, then boundary issues, then others.
    """
    failed_cases = [tc for tc in test_results if not tc.get("passed", False)]
    if not failed_cases:
        return None
        
    # Prioritize 'case_2_duplicates' because it probes key logical understandings
    for name in ["case_2_duplicates", "case_3_single_element"]:
        for fc in failed_cases:
            if fc.get("test_name") == name:
                return fc
                
    # Fallback to the first failed case
    return failed_cases[0]

def generate_question(failure_case: dict, rubric: dict) -> dict:
    """
    Generates a targeted diagnostic question based on the selected failure and the rubric.
    """
    test_name = failure_case.get("test_name")
    probes = rubric.get("diagnostic_probes", {})
    
    if test_name in probes:
        probe = probes[test_name]
        return {
            "question": probe.get("question"),
            "target_failure": test_name
        }
        
    # Default fallback question if not explicitly in rubric
    return {
        "question": f"For test case '{test_name}' with input {failure_case.get('input')}, your code returned {failure_case.get('actual')} instead of {failure_case.get('expected')}. What is causing this mismatch in your code?",
        "target_failure": test_name
    }

def evaluate_explanation(student_answer: str, failure_case_name: str, rubric: dict) -> dict:
    """
    Evaluates the student's answer against the rubric keywords.
    Returns structured results showing if it's correct and which keywords matched.
    """
    probes = rubric.get("diagnostic_probes", {})
    probe = probes.get(failure_case_name, {})
    keywords = probe.get("keywords", [])
    
    if not keywords:
        # Default simple fallback evaluation (accept any meaningful response with > 5 words)
        words = student_answer.strip().split()
        passed = len(words) >= 4
        return {
            "passed": passed,
            "matched_keywords": [],
            "feedback": "Your explanation was accepted." if passed else "Please provide a more detailed explanation of the bug."
        }
        
    # Perform case-insensitive keyword checking
    student_answer_lower = student_answer.lower()
    matched = [kw for kw in keywords if kw.lower() in student_answer_lower]
    
    # We require at least 1 keyword match for the explanation to be verified
    is_correct = len(matched) >= 1
    
    if is_correct:
        feedback = f"Excellent! Your explanation correctly identified key concepts: {', '.join(matched)}."
    else:
        feedback = "Your explanation doesn't seem to address the core problem (missing keywords related to: {}). Please think about what happens during sorting/retrieval with duplicates or single elements.".format(", ".join(keywords))
        
    return {
        "passed": is_correct,
        "matched_keywords": matched,
        "feedback": feedback
    }

def synthesize_final_verdict(original_results: list, student_answer: str, answer_eval: dict, revised_results: list) -> dict:
    """
    Cross-checks tests and explanation to produce a final verdict.
    """
    total_tests = len(revised_results)
    passed_tests = sum(1 for tc in revised_results if tc.get("passed", False))
    
    explanation_passed = answer_eval.get("passed", False)
    all_tests_passed = (passed_tests == total_tests)
    
    if all_tests_passed and explanation_passed:
        status = "BUGSTRIKER VERIFIED"
        confidence = "High"
        diagnosis = "Success! Both the explanation and revised code are fully correct and verified."
    elif all_tests_passed and not explanation_passed:
        status = "FINISHED"
        confidence = "Low"
        diagnosis = "Warning: The revised code passes all tests, but the explanation did not correctly identify the root cause. This suggests shallow debugging or lucky code changes."
    elif not all_tests_passed and explanation_passed:
        status = "FINISHED"
        confidence = "Low"
        diagnosis = "Partial: The explanation was correct, but the revised code still fails one or more test cases."
    else:
        status = "FINISHED"
        confidence = "None"
        diagnosis = "Failed: Both the explanation and revised code are incorrect. Please review the problem requirements."
        
    return {
        "status": status,
        "confidence": confidence,
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "diagnosis": diagnosis
    }
