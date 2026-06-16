import requests
import streamlit as st
import os
from urllib.parse import urlsplit

def fetch_image_variations(course_id):
    """Fetches image variations for a given course ID from the API.

    Args:
        course_id (str): The ID of the course.

    Returns:
        list[str]: A list of image URLs.

    Raises:
        requests.exceptions.RequestException: If there's an error making the API request.
    """

    url = f"http://localhost:8000/v2/image/variations/course/{course_id}"
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["images"]
    except requests.exceptions.RequestException as e:
        raise e

def get_filename_from_url(url=None):
    if url is None:
        return None
    urlpath = urlsplit(url).path
    return os.path.basename(urlpath)

def display_images(images):
    """Displays a list of image URLs in a 4-column grid.

    Args:
        images (list[str]): A list of image URLs.
    """

    cols = st.columns(4)
    for i, image_url in enumerate(images):
        print(image_url)
        cols[i].image(image_url, caption=  get_filename_from_url(image_url))

def main():
    """Main function for the Streamlit application."""

    st.title("Image Variation Generator")

    course_id = st.text_input("Enter Course ID:")

    generate_button = st.button("Generate Images")
    if generate_button:
        with st.spinner("Processing..."):
            try:
                images = fetch_image_variations(course_id)
                st.success("Images generated successfully!")
                display_images(images)
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching images: {e}")

if __name__ == "__main__":
    main()