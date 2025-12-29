import os
import asyncio
import tarfile, json, toml
from dotenv import load_dotenv

load_dotenv()
with open('config.toml', 'r') as f:
    config = toml.load(f)
class ImageExtarcter:
    def __init__(self, image_name):
        self.image_name = image_name
        self.tar_name = image_name.replace(':', '_').replace('/', '_').replace('.', '_')+".tar"
        self.tar_save_path = os.getenv("IMAGE_TAR_PATH") + f"/{self.tar_name.removesuffix('.tar')}"
        self.tar_file_path = f"{self.tar_save_path}/{self.tar_name}"
        if not os.path.exists(self.tar_save_path):
            os.mkdir(self.tar_save_path)

    async def save_image(self):
        if os.path.exists(self.tar_file_path):
            return True
        print("saving ", self.image_name)
        process = await asyncio.create_subprocess_exec(
            "docker",
            "save",
            self.image_name,
            "-o",
            self.tar_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if stderr:
            print(f"Image tar saved fail: {stderr.decode()}")
            return False
        return True
    
    async def unpack_image_tar(self):
        os.makedirs(self.tar_save_path, exist_ok=True)
        await asyncio.to_thread(self._sync_unpack_image)
        
    def _sync_unpack_image(self):
        if not os.path.exists(path=self.tar_file_path):
            raise FileNotFoundError(f"Tar file not found: {self.tar_file_path}")
        try:
            with tarfile.open(self.tar_file_path, 'r') as tar:
                tar.extractall(path=self.tar_save_path)
            print(f"All files extracted successfully to {self.tar_save_path}")
            os.remove(self.tar_file_path)
        except tarfile.ReadError as e:
            raise IOError(f"Read tar file error: {e}")
        except Exception as e:
            raise Exception(f"Unpack unknown error: {e}")

    async def check_layer_tar(self):
        layers_filename = await asyncio.to_thread(self._sync_check_layer_tar)
        return layers_filename, self.tar_name.removesuffix('.tar')

    def _sync_check_layer_tar(self):
        layers_filename = {}
        layer_tar_path = f"{self.tar_save_path}/blobs/sha256"
        layer_list = os.listdir(layer_tar_path)
        for layer in layer_list:
            # print(f"---- listing {layer} ------")
            try:
                with tarfile.open(f"{layer_tar_path}/{layer}") as tar:
                    files = tar.getnames()
                    filter_files = self.filter_file_name(files)
                    if filter_files != []:
                        layers_filename[layer] = filter_files
            except tarfile.ReadError as e:
                # print(f"Read layer tar failed: {e}")
                pass
            except Exception as e:
                # print(f"Unknown error: {e}")
                pass
        return layers_filename
    
    def filter_file_name(self, files):
        prefixes = tuple(config.get("PREFIX"))
        # keywords = set(config.get("LOW_PROBABILITY_KEYWORDS"))
        keywords = config.get("LOW_PROBABILITY_KEYWORDS")
        filtered = [
            item for item in files 
            if not (
                # 排除条件 A: 是否以任何低风险前缀开头？
                item.startswith(prefixes) 
                or
                # 排除条件 B: 路径组件中是否包含任何低概率关键字？
                # bool(set(item.split('/')).intersection(keywords)) 
                bool([k for k in keywords if k in item])
            )   
        ]
        return filtered

    def _sync_unpack_layer(self, layerid: str, filenames: list):
        layer_path = f"{self.tar_save_path}/blobs/sha256/{layerid}"
        os.makedirs(f"{self.tar_save_path}/file_with_creds/{layerid}", exist_ok=True)
        for filename in filenames:
            with tarfile.open(layer_path, 'r') as tar:
                tar.extract(filename, path=f"{self.tar_save_path}/file_with_creds/{layerid}")
                print(f"Unpack {filename}....")
    
    async def unpack_layer(self, layerids: list, filenames: dict) -> str:
        os.makedirs(f"{self.tar_save_path}/file_with_creds", exist_ok=True)
        for layerid in layerids:
            if not os.path.exists(f"{self.tar_save_path}/file_with_creds/{layerid}"):
                await asyncio.to_thread(self._sync_unpack_layer, layerid, filenames[layerid])
                print(f"Unpack {layerid} successfully")
        return f"{self.tar_save_path}/file_with_creds"

async def main():
    extracter = ImageExtarcter("docker-registry.cobasi.com.br/pwa-service:dev")
    # await extracter.save_image()
    # await extracter.unpack_image_tar()
    print(await extracter.check_layer_tar())

if __name__ == "__main__":
    asyncio.run(main())