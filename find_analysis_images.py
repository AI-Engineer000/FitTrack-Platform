import cv2

for name in ['Milestone 3_macro_image2.png', 'Milestone 3_macro_image3.png', 'Milestone 3_macro_image4.png']:
    im = cv2.imread('poster_screenshots/' + name)
    print(name, 'shape:', im.shape, 'mean:', im.mean(axis=(0,1)).astype(int))
