import time

chapter: str = 'Загружаю главу "Глава {number}"'

print('Сайт https://api.author.today/ доступен. Работаю через него')
time.sleep(0.3)
print('Начинаю генерацию книги "https://author.today/work/294045"')
time.sleep(0.3)
print('Загружена картинка https://author.today/content/2023/09/06/826a8a75b64146108aa3538453812b87.jpg')
time.sleep(0.3)

for i in range(1,5):
    print(chapter.format(number=i))
    time.sleep(1)

print('Начинаю сохранение книги ".\Юрий Винокуров - Кодекс Охотника. Книга XV.fb2"')
time.sleep(0.3)
print('Книга ".\Юрий Винокуров - Кодекс Охотника. Книга XV.fb2" успешно сохранена')
time.sleep(0.3)
print('Начинаю сохранение книги ".\Юрий Винокуров - Кодекс Охотника. Книга XV.json"')
time.sleep(0.3)
print('Книга ".\Юрий Винокуров - Кодекс Охотника. Книга XV.json" успешно сохранена')