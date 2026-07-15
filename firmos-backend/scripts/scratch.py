import sys
import asyncio
sys.path.append('.')
from core.config import settings
from extraction.sarvam import _run_sarvam_pipeline

async def main():
    with open("../apps/web/public/samples/vendor-bill-1.jpg", "rb") as f:
        data = f.read()
    
    try:
        res = await _run_sarvam_pipeline(data, "image/jpeg")
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
