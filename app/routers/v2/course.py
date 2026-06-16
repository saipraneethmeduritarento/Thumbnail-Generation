import time
from fastapi import APIRouter, HTTPException
from ...logger import logger
from ...models import ImageVariationResponse
from ...services.v2.image_variation import generate_image_variations

router = APIRouter(
    tags=["Course"]
)

@router.get(
    "/variations/course/{course_id}",
    response_model=ImageVariationResponse,
    summary="Generate thumbnail variations from an existing course thumbnail",
    responses={
        500: {"description": "Something went wrong, please try again later..."}
    },
)
def generate_course_image_variations(course_id: str):
    try:
        start_time = time.time()
        logger.info(f"Course ID : {course_id}")
        logo_detection, image_urls = generate_image_variations(course_id)
        print("Time took to process the request and return response is {} sec".format(time.time() - start_time))
        return ImageVariationResponse(images=image_urls, logo=logo_detection)
    except Exception:
        logger.exception("Error while generating the image variations")
        raise HTTPException(status_code=500, detail=str("Something went wrong, please try again later..."))

    