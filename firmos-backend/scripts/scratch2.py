import sys
import asyncio
sys.path.append('.')
from core.config import settings
from extraction.sarvam import _run_sarvam_pipeline

async def main():
    with open("uploads/doc-33e143e5.image", "rb") as f:
        data = f.read()
    
    try:
        res = await _run_sarvam_pipeline(data, "image/jpeg")
        print("EXTRACTION SUCCESSFUL:")
        print(res)
    except Exception as e:
        print("EXTRACTION FAILED:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
