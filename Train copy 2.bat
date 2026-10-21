set "src=D:\yoloTrain\runs\detect\train\weights\best.pt"
set "dst1=D:\docker\LM-Backend\label-studio-ml-backend\label_studio_ml\examples\yolo\models\best.pt"
set "dst2=d:\rice_anomaly_detection_PyTorch\models\yolo\best.pt"
set "dst3=D:\yoloTrain\best.pt"

if exist "%src%" (
    copy /Y "%src%" "%dst1%"
    copy /Y "%src%" "%dst2%"
    copy /Y "%src%" "%dst3%"
    echo [OK] Model updated and backed up.
) else (
    echo [!] Error: source file not found.
)
