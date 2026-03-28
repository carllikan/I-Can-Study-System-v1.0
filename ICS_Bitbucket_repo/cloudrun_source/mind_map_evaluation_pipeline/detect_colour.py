from collections import Counter
import numpy as np
def colordetect(rgb_value):
    """
    Detects a color name based on the given RGB value by checking predefined RGB ranges for common colors.
    If the RGB value does not fall within any predefined range, the function calculates the closest color 
    based on Euclidean distance in the RGB color space.

    Parameters:
    - rgb_value (tuple): A tuple of RGB values in the form (R, G, B), where each value is an integer from 0 to 255.

    Returns:
    - str: The name of the detected color, or 'UNKNOWN' if the color does not closely match any predefined colors.
    """
    # Define RGB ranges for common colors
    color_ranges = {
        'RED': [(200, 0, 0), (255, 80, 80)],
        'GREEN': [(0, 100, 0), (150, 255, 150)],
        'BLUE': [(0, 0, 200), (80, 80, 255)],
        'YELLOW': [(200, 200, 0), (255, 255, 80)],
        'ORANGE': [(255, 120, 0), (255, 200, 50)],
        'PURPLE': [(75, 0, 130), (160, 80, 255)],
        'CYAN': [(0, 200, 200), (80, 255, 255)],
        'MAGENTA': [(200, 0, 200), (255, 80, 255)],
        'BLACK': [(0, 0, 0), (50, 50, 50)],
        'WHITE': [(240, 240, 240), (255, 255, 255)]
        # Add more colors with specific ranges as needed
    }

    closest_color = 'UNKNOWN'
    min_distance = float('inf')

    # Check if the color is within any of the defined ranges
    for color, (lower_bound, upper_bound) in color_ranges.items():
        if all(lower_bound[i] <= rgb_value[i] <= upper_bound[i] for i in range(3)):
            return color

    # If not within range, find the closest color based on distance
    r1, g1, b1 = rgb_value
    for color, bounds in color_ranges.items():
        lower_bound, upper_bound = bounds
        # Calculate distance to the mid-point of the lower and upper bounds
        r2, g2, b2 = [(lb + ub) / 2 for lb, ub in zip(lower_bound, upper_bound)]
        distance = ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            closest_color = color

    return closest_color

def nodes_addcolor(nodes_df, image):
    """
    Function to add color information to the nodes DataFrame based on the colors within their bounding boxes.
    Handles both PNG (possibly with alpha channel) and JPEG images.

    Args:
        nodes_df (pd.DataFrame): DataFrame containing node information with 'xmin', 'ymin', 'xmax', 'ymax' columns.
        image (PIL.Image): Image from which to extract color data.

    Returns:
        pd.DataFrame: Updated DataFrame with a new 'color' column indicating the most common color in each node's bounding box.
    """
    # Convert the PIL image to a numpy array
    image_np = np.array(image)
    num_channels = image_np.shape[2] if len(image_np.shape) > 2 else 1  # Check the number of channels

    # Iterate over each row in the DataFrame to process bounding boxes
    for index, row in nodes_df.iterrows():
        left, top, right, bottom = map(int, [row["xmin"], row["ymin"], row["xmax"], row["ymax"]])
        color_counts = Counter()

        # Iterate through pixels in the bounding box
        for x in range(left, min(right, image_np.shape[1])):
            for y in range(top, min(bottom, image_np.shape[0])):
                rgb_value = image_np[y, x]
                if num_channels == 4:  # If RGBA, strip the Alpha channel
                    rgb_value = rgb_value[:3]
                if all(val > 0 for val in rgb_value):  # Filter out black pixels
                    detected_color = colordetect(tuple(rgb_value))
                    color_counts[detected_color] += 1

        # Optional: filter out white if it's overly dominant
        if color_counts.get('WHITE', 0) > 240:
            del color_counts['WHITE']

        # Find the most common color or default to 'BLACK'
        most_common_color = color_counts.most_common(1)[0][0] if color_counts else 'BLACK'
        nodes_df.at[index, "color"] = most_common_color

    return nodes_df
