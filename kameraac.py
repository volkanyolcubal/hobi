import cv2

cap = cv2.VideoCapture(0) # 0, varsayılan kameradır

while True:
    ret, frame = cap.read()
    cv2.imshow('Kamera', frame)

    # Çıkmak için 'q' tuşuna bas
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
