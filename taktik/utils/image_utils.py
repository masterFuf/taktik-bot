import os
import base64
import requests
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger
from PIL import Image
import io


def compress_image(image_path: str, max_size_kb: int = 50, quality: int = 85) -> Optional[str]:
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Image non trouvée: {image_path}")
            return None
        
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            max_dimension = 512
            if max(img.size) > max_dimension:
                ratio = max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Image redimensionnée de {image_path.name}: {img.size}")
            
            compressed_path = image_path.parent / f"compressed_{image_path.stem}.jpg"
            
            current_quality = quality
            while current_quality > 10:
                img.save(compressed_path, 'JPEG', quality=current_quality, optimize=True)
                
                file_size_kb = compressed_path.stat().st_size / 1024
                
                if file_size_kb <= max_size_kb:
                    logger.success(f"Image compressée: {file_size_kb:.1f}KB (qualité: {current_quality})")
                    return str(compressed_path)
                
                current_quality -= 10
                logger.debug(f"Taille trop grande ({file_size_kb:.1f}KB), réduction qualité à {current_quality}")
            
            logger.warning(f"Impossible d'atteindre {max_size_kb}KB, taille finale: {file_size_kb:.1f}KB")
            return str(compressed_path)
            
    except Exception as e:
        logger.error(f"Erreur lors de la compression de l'image: {e}")
        return None


def image_to_base64(image_path: str) -> Optional[str]:
    try:
        with open(image_path, 'rb') as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        logger.error(f"Erreur lors de l'encodage base64: {e}")
        return None


def upload_profile_image(image_path: str, username: str, api_base_url: str, api_key: str) -> Optional[str]:
    try:
        # Compresser l'image d'abord
        compressed_path = compress_image(image_path)
        if not compressed_path:
            logger.error("Échec de la compression de l'image")
            return None
        
        base64_image = image_to_base64(compressed_path)
        if not base64_image:
            logger.error("Échec de l'encodage base64")
            return None
        
        image_extension = compressed_path.split('.')[-1].lower()
        if image_extension not in ['jpg', 'jpeg', 'png', 'gif']:
            image_extension = 'jpg'  # Par défaut
        
        upload_data = {
            'username': username,
            'image_data': base64_image,
            'image_type': image_extension
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        upload_url = f"{api_base_url}/upload/profile-image"
        response = requests.post(upload_url, json=upload_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            image_url = result.get('image_url')
            if image_url:
                logger.success(f"Image uploadée avec succès: {image_url}")
                
                try:
                    os.remove(compressed_path)
                    os.remove(image_path)  # Supprimer l'original aussi
                    logger.debug("Fichiers temporaires nettoyés")
                except:
                    pass
                
                return image_url
            else:
                logger.error("URL d'image non retournée par l'API")
        else:
            logger.error(f"Échec de l'upload: {response.status_code} - {response.text}")
        
        return None
        
    except Exception as e:
        logger.error(f"Erreur lors de l'upload de l'image: {e}")
        return None


def process_profile_image(local_image_path: str, username: str, 
                         api_base_url: str = None, api_key: str = None) -> str:
    try:
        if api_base_url and api_key:
            uploaded_url = upload_profile_image(local_image_path, username, api_base_url, api_key)
            if uploaded_url:
                return uploaded_url
            else:
                logger.warning("Échec de l'upload, conservation du fichier local")
        
        compressed_path = compress_image(local_image_path)
        if compressed_path:
            try:
                os.remove(local_image_path)
            except:
                pass
            return compressed_path
        
        return local_image_path
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'image: {e}")
        return local_image_path
