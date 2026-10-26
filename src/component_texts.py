"""User-facing component actions/errors in every supported UI language."""
TEXT = {
 'en': ('Update RapidOCR', 'No tested compatible update is available for this system and update channel.', 'The update catalog could not be verified or reached. The installed engine is unchanged.', 'The component could not be installed. The previous working version is unchanged.'),
 'ru': ('Обновить RapidOCR', 'Для этой системы и канала обновлений пока нет проверенного совместимого обновления.', 'Не удалось получить или проверить каталог обновлений. Установленный движок не изменён.', 'Не удалось установить компонент. Прежняя рабочая версия сохранена.'),
 'es': ('Actualizar RapidOCR', 'No hay una actualización compatible y verificada para este sistema y canal.', 'No se pudo obtener o verificar el catálogo. El motor instalado no ha cambiado.', 'No se pudo instalar el componente. Se conserva la versión anterior.'),
 'de': ('RapidOCR aktualisieren', 'Für dieses System und diesen Kanal ist kein geprüftes kompatibles Update verfügbar.', 'Der Updatekatalog konnte nicht geladen oder geprüft werden. Die installierte Engine bleibt erhalten.', 'Die Komponente konnte nicht installiert werden. Die bisherige Version bleibt erhalten.'),
 'fr': ('Mettre à jour RapidOCR', 'Aucune mise à jour compatible et vérifiée n’est disponible pour ce système et ce canal.', 'Impossible de récupérer ou de vérifier le catalogue. Le moteur installé reste inchangé.', 'Impossible d’installer le composant. La version précédente est conservée.'),
 'zh': ('更新 RapidOCR', '此系统和更新渠道尚无经过测试的兼容更新。', '无法获取或验证更新目录。已安装的引擎保持不变。', '无法安装组件。已保留原来可用的版本。'),
 'pt': ('Atualizar RapidOCR', 'Não há atualização compatível e testada para este sistema e canal.', 'Não foi possível obter ou verificar o catálogo. O motor instalado não foi alterado.', 'Não foi possível instalar o componente. A versão anterior foi preservada.'),
 'it': ('Aggiorna RapidOCR', 'Non è disponibile un aggiornamento compatibile e verificato per questo sistema e canale.', 'Impossibile ottenere o verificare il catalogo. Il motore installato non è stato modificato.', 'Impossibile installare il componente. La versione precedente è stata conservata.'),
 'ar': ('تحديث RapidOCR', 'لا يتوفر تحديث متوافق ومختبَر لهذا النظام وقناة التحديث.', 'تعذر جلب كتالوج التحديثات أو التحقق منه. لم يتغير المحرك المثبت.', 'تعذر تثبيت المكوّن. تم الاحتفاظ بالإصدار السابق الذي يعمل.'),
 'tr': ('RapidOCR güncelle', 'Bu sistem ve kanal için test edilmiş uyumlu bir güncelleme yok.', 'Güncelleme kataloğu alınamadı veya doğrulanamadı. Kurulu motor değiştirilmedi.', 'Bileşen kurulamadı. Önceki çalışan sürüm korundu.'),
 'hi': ('RapidOCR अपडेट करें', 'इस सिस्टम और अपडेट चैनल के लिए जाँचा हुआ संगत अपडेट उपलब्ध नहीं है।', 'अपडेट सूची प्राप्त या सत्यापित नहीं हो सकी। स्थापित इंजन नहीं बदला गया है।', 'घटक स्थापित नहीं हो सका। पिछला काम करने वाला संस्करण सुरक्षित है।'),
 'id': ('Perbarui RapidOCR', 'Belum ada pembaruan kompatibel yang teruji untuk sistem dan kanal ini.', 'Katalog pembaruan tidak dapat diambil atau diverifikasi. Mesin terpasang tidak berubah.', 'Komponen tidak dapat dipasang. Versi sebelumnya yang berfungsi tetap disimpan.'),
}


def update_label(language):
    return TEXT.get(language, TEXT['en'])[0]


UPDATE_HINTS = {
 'en': 'Download and install the latest tested compatible RapidOCR. A failed update preserves the working version.',
 'ru': 'Скачать и установить последнюю проверенную совместимую версию RapidOCR. При ошибке рабочая версия сохранится.',
 'es': 'Descargar e instalar la última versión compatible y probada de RapidOCR. Si falla, se conserva la versión anterior.',
 'de': 'Die neueste geprüfte kompatible RapidOCR-Version installieren. Bei Fehlern bleibt die bisherige Version erhalten.',
 'fr': 'Télécharger et installer la dernière version compatible et vérifiée de RapidOCR. En cas d’échec, la version précédente est conservée.',
 'zh': '下载并安装最新的已测试兼容 RapidOCR。更新失败时保留原来的可用版本。',
 'pt': 'Baixar e instalar a versão compatível e testada mais recente do RapidOCR. Em caso de falha, a versão anterior é preservada.',
 'it': 'Scarica e installa l’ultima versione compatibile e verificata di RapidOCR. In caso di errore, la versione precedente viene conservata.',
 'ar': 'تنزيل أحدث إصدار متوافق ومختبَر من RapidOCR وتثبيته. عند فشل التحديث يُحتفظ بالإصدار الذي يعمل.',
 'tr': 'RapidOCR’nin test edilmiş en yeni uyumlu sürümünü indirip kurar. Hata durumunda çalışan sürüm korunur.',
 'hi': 'RapidOCR का नवीनतम जाँचा हुआ संगत संस्करण डाउनलोड और स्थापित करें। विफल होने पर काम करने वाला संस्करण सुरक्षित रहेगा।',
 'id': 'Unduh dan pasang versi RapidOCR kompatibel terbaru yang telah diuji. Jika gagal, versi yang berfungsi tetap disimpan.',
}


def error_text(language, error):
    values = TEXT.get(language, TEXT['en'])
    code = getattr(error, 'code', '')
    index = 1 if code == 'no_compatible_update' else 2 if code in ('catalog_unavailable', 'update_client_missing') else 3
    return values[index] + (f' [{code}]' if code else '')
