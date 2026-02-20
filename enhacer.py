import os
import cv2
import torch
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

class MangaEnhancer:
    def __init__(self):
        # Configuração do dispositivo de hardware
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Enhancer iniciado no dispositivo: {self.device}")
        
        # O modelo focado em anime usa a arquitetura RRDBNet com parâmetros específicos
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
        
        # Inicializando o upscaler
        self.upsampler = RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth',
            model=model,
            tile=0,        # Aumente se faltar VRAM (ex: 256)
            tile_pad=10,
            pre_pad=0,
            half=True if self.device.type == 'cuda' else False, # fp16 acelera muito na GPU
            device=self.device
        )

    def process_chapter(self, chapter_folder):
        """Itera sobre as imagens da pasta e aplica o Real-ESRGAN."""
        for filename in sorted(os.listdir(chapter_folder)):
            if filename.lower().endswith(('.jpg', '.png', '.jpeg')):
                img_path = os.path.join(chapter_folder, filename)
                
                print(f"Aprimorando: {filename}...")
                img = cv2.imread(img_path, cv2.IMREAD_COLOR)
                
                try:
                    # Aplica o upscale
                    output, _ = self.upsampler.enhance(img, outscale=4)
                    
                    # Gera o novo nome de arquivo com o sufixo
                    name, ext = os.path.splitext(filename)
                    out_path = os.path.join(chapter_folder, f"{name}_upscaled{ext}")
                    
                    cv2.imwrite(out_path, output)
                except Exception as e:
                    print(f"Falha ao processar {filename}: {e}")