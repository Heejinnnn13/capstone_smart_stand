import time
import json
import os

class StudySessionManager:
    def __init__(self, save_path="study_sessions.json"):
        self.current_subject = None
        self.start_time = None
        self.save_path = save_path

        if not os.path.exists(self.save_path):
            with open(self.save_path, "w") as f:
                json.dump([], f)

    def change_subject(self, new_subject):
        now = time.time()

        if self.current_subject is not None:
            duration = int(now - self.start_time)
            print(f"[SUBJECT] END {self.current_subject} ({duration}s)", flush=True)
            self._save_session(self.current_subject, self.start_time, now)

        self.current_subject = new_subject
        self.start_time = now
        print(f"[SUBJECT] START {new_subject}", flush=True)

    def _save_session(self, subject, start, end):
        session_data = {
            "subject": subject,
            "start": start,
            "end": end,
            "duration_sec": int(end - start),
        }

        with open(self.save_path, "r") as f:
            data = json.load(f)

        data.append(session_data)

        with open(self.save_path, "w") as f:
            json.dump(data, f, indent=4)
