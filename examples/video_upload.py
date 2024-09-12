import asyncio
import json
import os
import time

import google.generativeai as genai
from fastapi import File, UploadFile

import realtime as rt


@rt.App()
class VideoSurveillanceApp:
    @rt.web_endpoint(method="POST", path="/submit")
    async def run(file: UploadFile = File(None), prompt: str = ""):
        directory = "data"
        filename = file.filename
        file_path = os.path.join(directory, filename)

        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)
        start_time = time.time()
        try:
            try:
                with open(file_path, "wb") as f:
                    contents = file.file.read()
                    f.write(contents)
            except Exception:
                return {"message": "There was an error uploading the file"}
            finally:
                file.file.close()

            print("Uploading file...", time.time() - start_time)
            video_file = genai.upload_file(path=file_path)
            print(f"Completed upload: {video_file.uri}", time.time() - start_time)

            while video_file.state.name == "PROCESSING":
                print("Waiting for video to be processed.")
                time.sleep(1)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                raise ValueError(video_file.state.name)

            print(
                "Video processing complete: " + video_file.uri,
                time.time() - start_time,
            )

            if not prompt:
                prompt = "Detect if an accident happened in the video."

            prompt += " Output a JSON with 'accident' set to True/False, 'time' in the video the accident happened and 'description' of the accident."

            # Set the model to Gemini 1.5 Flash.
            model = genai.GenerativeModel(
                model_name="models/gemini-1.5-flash",
                generation_config={"response_mime_type": "application/json"},
            )

            # Make the LLM request.
            print("Making LLM inference request...", time.time() - start_time)
            response = model.generate_content(
                [prompt, video_file], request_options={"timeout": 600}
            )
            print("LLM inference request complete", time.time() - start_time)
        except Exception as e:
            return {"message": f"There was an error processing the file {e}"}

        return {
            "file": file.filename,
            "response": json.dumps(json.loads(response.text), indent=4),
        }


if __name__ == "__main__":
    asyncio.run(VideoSurveillanceApp().run())
