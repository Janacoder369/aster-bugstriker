import http.server
import socketserver
import json
import os
import sys
import uuid
from urllib.parse import urlparse

# Add current folder to path to import local modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import runner
import evaluator

# Paths
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
STORE_PATH = os.path.join(DATA_DIR, "store.json")
RUBRIC_PATH = os.path.join(DATA_DIR, "rubric.json")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Port to listen on
PORT = 8000

def load_rubric() -> dict:
    """Loads the fixed task rubric."""
    if not os.path.exists(RUBRIC_PATH):
        # Default rubric if missing
        default_rubric = {
            "problem_id": "second_largest",
            "title": "Second Largest Distinct Number",
            "description": "Write a function second_largest(a) that takes a list of integers and returns the second-largest distinct number in the list. If there is no such number (e.g. list has fewer than 2 distinct elements), return the string 'invalid input'.",
            "test_cases": [
                {"name": "case_1_distinct", "input": "[5, 1, 9, 3]", "expected": "5"},
                {"name": "case_2_duplicates", "input": "[5, 5, 2]", "expected": "2"},
                {"name": "case_3_single_element", "input": "[7]", "expected": "\"invalid input\""}
            ],
            "diagnostic_probes": {
                "case_2_duplicates": {
                    "question": "For [5, 5, 2], your code returns 5 (or fails). What does sorting and selecting an index (like a[-2]) do when duplicates are present, and why is that not necessarily the second-largest distinct value?",
                    "keywords": ["duplicate", "set", "unique", "distinct", "same", "remove"]
                },
                "case_3_single_element": {
                    "question": "For [7], your code fails or returns an incorrect value. How should your code handle lists with fewer than 2 distinct elements, and what does the rubric require in that case?",
                    "keywords": ["invalid", "fewer", "length", "less", "single", "one", "element"]
                }
            }
        }
        with open(RUBRIC_PATH, "w", encoding="utf-8") as f:
            json.dump(default_rubric, f, indent=2)
        return default_rubric
        
    with open(RUBRIC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_store() -> dict:
    """Loads run history store."""
    if not os.path.exists(STORE_PATH):
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_store(store: dict):
    """Saves run history store."""
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)

class BugStrikerHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _send_html(self, content_str, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content_str.encode('utf-8'))

    def _send_file(self, file_path, content_type):
        if not os.path.exists(file_path):
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/" or path == "/index.html":
            html_path = os.path.join(TEMPLATES_DIR, "index.html")
            if os.path.exists(html_path):
                self._send_file(html_path, "text/html")
            else:
                self._send_html("<h1>BugStriker Server is Running!</h1><p>But index.html is missing in templates folder.</p>")
            return

        elif path == "/api/problem":
            rubric = load_rubric()
            # Clean up the rubric slightly to hide exact keywords from student
            clean_rubric = {
                "problem_id": rubric["problem_id"],
                "title": rubric["title"],
                "description": rubric["description"],
                "test_cases": [
                    {"name": tc["name"], "input": tc["input"], "expected": tc["expected"]}
                    for tc in rubric["test_cases"]
                ]
            }
            self._send_json(clean_rubric)
            return

        elif path.startswith("/api/run/"):
            run_id = path.split("/")[-1]
            store = load_store()
            if run_id in store:
                self._send_json(store[run_id])
            else:
                self._send_json({"error": "Run session not found"}, 404)
            return

        elif path == "/api/runs":
            store = load_store()
            # Return high-level summary of runs
            summaries = []
            for rid, rdata in store.items():
                summaries.append({
                    "run_id": rid,
                    "student_id": rdata.get("student_id"),
                    "status": rdata.get("status"),
                    "score": rdata.get("final_evaluation", {}).get("passed_tests", 0),
                    "total": rdata.get("final_evaluation", {}).get("total_tests", len(rdata.get("original_test_results", [])))
                })
            self._send_json(summaries)
            return

        # Handle static files if any exist
        elif path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            # basic directory traversal guard
            if ".." in relative_path:
                self.send_error(400, "Bad Request")
                return
            file_path = os.path.join(STATIC_DIR, relative_path)
            
            # Determine content type
            if file_path.endswith(".css"):
                content_type = "text/css"
            elif file_path.endswith(".js"):
                content_type = "application/javascript"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".gif"):
                content_type = "image/gif"
            else:
                content_type = "application/octet-stream"
                
            self._send_file(file_path, content_type)
            return

        else:
            self.send_error(404, "Page not found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # Read JSON body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode('utf-8')) if post_data else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, 400)
            return

        if path == "/api/submit":
            # Start of a new submission run
            student_id = body.get("student_id", "Anonymous")
            code = body.get("code", "").strip()
            
            if not code:
                self._send_json({"error": "Code cannot be empty"}, 400)
                return

            rubric = load_rubric()
            run_id = str(uuid.uuid4())
            
            # STATE: SUBMITTED -> RUNNING_TESTS
            print(f"[Run {run_id}] State transition: SUBMITTED -> RUNNING_TESTS")
            original_test_results = runner.run_tests(code, rubric["test_cases"])
            
            # Check if there are failures
            failed_cases = [tc for tc in original_test_results if not tc.get("passed", False)]
            
            store = load_store()
            
            if not failed_cases:
                # Student code is 100% correct immediately!
                # STATE: RUNNING_TESTS -> ANALYZING -> FINISHED (Verified)
                print(f"[Run {run_id}] All tests passed on initial submission. State: FINISHED.")
                run_data = {
                    "run_id": run_id,
                    "student_id": student_id,
                    "problem_id": rubric["problem_id"],
                    "status": "FINISHED",
                    "original_code": code,
                    "original_test_results": original_test_results,
                    "selected_failure": None,
                    "question": None,
                    "student_answer": None,
                    "answer_evaluation": None,
                    "revised_code": code,
                    "revised_test_results": original_test_results,
                    "final_evaluation": {
                        "status": "BUGSTRIKER VERIFIED",
                        "confidence": "High",
                        "passed_tests": len(rubric["test_cases"]),
                        "total_tests": len(rubric["test_cases"]),
                        "diagnosis": "Excellent! Your code is fully correct and passes all tests on your first submission!"
                    }
                }
            else:
                # STATE: RUNNING_TESTS -> ANALYZING
                print(f"[Run {run_id}] Found failures. State: ANALYZING.")
                selected_failure = evaluator.select_failure(original_test_results)
                
                # STATE: ANALYZING -> QUESTIONING -> WAITING_FOR_STUDENT
                print(f"[Run {run_id}] State: QUESTIONING -> WAITING_FOR_STUDENT.")
                question_record = evaluator.generate_question(selected_failure, rubric)
                
                run_data = {
                    "run_id": run_id,
                    "student_id": student_id,
                    "problem_id": rubric["problem_id"],
                    "status": "WAITING_FOR_STUDENT",
                    "original_code": code,
                    "original_test_results": original_test_results,
                    "selected_failure": selected_failure,
                    "question": question_record["question"],
                    "student_answer": None,
                    "answer_evaluation": None,
                    "revised_code": None,
                    "revised_test_results": None,
                    "final_evaluation": None
                }
                
            store[run_id] = run_data
            save_store(store)
            self._send_json(run_data)
            return

        elif path == "/api/answer":
            # Student answers the diagnostic question and submits a code revision
            run_id = body.get("run_id")
            answer_text = body.get("answer", "").strip()
            revised_code = body.get("revised_code", "").strip()
            
            if not run_id:
                self._send_json({"error": "Missing run_id"}, 400)
                return
                
            store = load_store()
            if run_id not in store:
                self._send_json({"error": "Run session not found"}, 404)
                return
                
            run_data = store[run_id]
            if run_data["status"] != "WAITING_FOR_STUDENT":
                self._send_json({"error": "This run is not awaiting a student response"}, 400)
                return
                
            if not answer_text:
                self._send_json({"error": "Explanation answer cannot be empty"}, 400)
                return
                
            if not revised_code:
                self._send_json({"error": "Revised code cannot be empty"}, 400)
                return

            rubric = load_rubric()
            
            # STATE: WAITING_FOR_STUDENT -> REVISION
            print(f"[Run {run_id}] State transition: WAITING_FOR_STUDENT -> REVISION")
            run_data["student_answer"] = answer_text
            run_data["revised_code"] = revised_code
            
            # Evaluate explanation
            target_failure_name = run_data["selected_failure"]["test_name"]
            answer_eval = evaluator.evaluate_explanation(answer_text, target_failure_name, rubric)
            run_data["answer_evaluation"] = answer_eval
            
            # STATE: REVISION -> RUNNING_TESTS
            print(f"[Run {run_id}] State transition: REVISION -> RUNNING_TESTS")
            revised_test_results = runner.run_tests(revised_code, rubric["test_cases"])
            run_data["revised_test_results"] = revised_test_results
            
            # STATE: RUNNING_TESTS -> ANALYZING -> FINISHED
            print(f"[Run {run_id}] State transition: RUNNING_TESTS -> ANALYZING -> FINISHED")
            final_eval = evaluator.synthesize_final_verdict(
                run_data["original_test_results"],
                answer_text,
                answer_eval,
                revised_test_results
            )
            run_data["final_evaluation"] = final_eval
            run_data["status"] = "FINISHED"
            
            store[run_id] = run_data
            save_store(store)
            self._send_json(run_data)
            return

        elif path == "/api/reset":
            # Deletes all sessions or starts a fresh run
            save_store({})
            self._send_json({"message": "Successfully cleared history and reset sessions"})
            return

        else:
            self.send_error(404, "Endpoint not found")

def run_server():
    # Load or initialize rubric on startup
    load_rubric()
    load_store()
    
    # Configure socket server to allow port reuse immediately
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), BugStrikerHandler) as httpd:
        print(f"BugStriker server successfully started at: http://localhost:{PORT}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping BugStriker server...")
            sys.exit(0)

if __name__ == "__main__":
    run_server()
