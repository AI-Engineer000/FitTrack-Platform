import cv2

from measurements.profile import get_height, get_weight


def main():
    height = get_height()
    weight = get_weight()

    print(f"Athlete Height: {height} cm")
    print(f"Athlete Weight: {weight} kg")


if __name__ == "__main__":
    main()
