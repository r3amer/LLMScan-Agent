import argparse
import asyncio
import os
import sys
import json
from llm_scanner import LLMScanner
from image_extract import ImageExtarcter

# def main():
#     parser = argparse.ArgumentParser(
#         description="Image scan with LLM",
#         formatter_class=argparse.RawTextHelpFormatter
#     )
    
#     parser.add_argument(
#         "--api-key", 
#         type=str, 
#         default=os.environ.get("GEMINI_API_KEY"),
#     )
    
#     parser.add_argument(
#         "--model", 
#         type=str, 
#         default="gemini-2.5-flash",
#     )
    
#     parser.add_argument(
#         "--max-size", 
#         type=int, 
#         default=5, 
#     )
#     args = parser.parse_args()

def analyse_batch_filenames(scanner: LLMScanner, current_filenames):
    resp = scanner.analyze_filenames(json.dumps(current_filenames))
    if "error" in resp.keys():
        print(f"[-] Analyze failed. {resp['error']} {current_filenames.keys()}")
        return {}
    return resp

def analyse_filenames(scanner, layers_filename):
    max_length = 5000
    current_len = 0
    current_filenames = {}
    result = ""
    layer_ids = list(layers_filename.keys())
    for layer_id in layer_ids:
        print(json.dumps(layers_filename[layer_id]))
        current_len += len(json.dumps(layers_filename[layer_id]))
        print(current_len)
        if current_len < max_length:
            current_filenames[layer_id] = layers_filename[layer_id]
        else:
            print(f"Length of filenames: {len(json.dumps(current_filenames))}")
            resp = analyse_batch_filenames(scanner, current_filenames)
            print(resp)
            if resp:
                result = result + json.dumps(resp)[1:-1] + ","
            current_len = len(json.dumps(layers_filename[layer_id]))
            current_filenames = {layer_id: layers_filename[layer_id]}
    resp = analyse_batch_filenames(scanner, current_filenames)
    if resp:
        result = result + json.dumps(resp)[1:-1] + ","
    result = json.loads("{" + result.strip(",") + "}")
    return result

async def main():
    extracter = ImageExtarcter("112.175.148.5:5000/wert/backoffice/server")
    api_key = os.environ.get('GEMINI_API_KEY')
    scanner = LLMScanner(api_key=api_key, model_name="gemini-2.5-flash")
    # await extracter.save_image()
    # await extracter.unpack_image_tar()
    layers_filename, image_name = await extracter.check_layer_tar()
    json_file_name = image_name + ".json"

    # analyse filenames
    print("Analyzing filenames...")
    result = analyse_filenames(scanner, layers_filename)
    with open(json_file_name, 'w') as f:
        json.dump(result ,f, indent = 4)
    print("[+] Analyzing filenames finished.")

    # save layer info as json file
    with open(json_file_name, 'r') as f:
        filenames = json.load(f)

    # analyse file contents
    print("Unpacking layers...")
    try:
        secret_file_path = await extracter.unpack_layer(filenames.keys(), filenames)
        print("[+] Unpack layers finished.")
    except Exception as e:
        print(f"[-] Unpack layers failed. {e}")

    print("Analyzing file contents...")
    secrets_path = f"tmp/secrets/{image_name}"
    os.makedirs(secrets_path, exist_ok=True)
    for layerid in filenames.keys():
        os.makedirs(f"{secrets_path}/{layerid}", exist_ok=True)
        for filename in filenames[layerid]:
            print(f"------ {filename} ------")
            if os.path.isdir(f"{secret_file_path}/{layerid}/{filename}"):
                continue
            with open(f"{secret_file_path}/{layerid}/{filename}", 'r') as f:
                file_content= repr(f.read())
            # print(len(file_content))
        
            resp = scanner.analyze_file_contents(file_content)
            secret_json = filename.replace('.','_').replace('/', '_')
            print(len(json.dumps(resp)))
            if not resp.get("secrets",[]):
                continue
            while resp.get("api call error", ""):
                resp = scanner.analyze_file_contents(file_content)
                print(len(json.dumps(resp)))
            with open(f"{secrets_path}/{layerid}/{secret_json}.json", 'w') as f:
                json.dump(resp, f, indent=4, ensure_ascii=False)
        if not os.listdir(f"{secrets_path}/{layerid}"):
            os.rmdir(f"{secrets_path}/{layerid}")
    print("[+] Analyzing file contents finished")
if __name__ == "__main__":
    asyncio.run(main())