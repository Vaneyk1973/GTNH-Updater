# GTNH Updater

[English](README.md) · [Проверки](docs/TESTING.md) · [Сборка и публикация](docs/RELEASING.md)

Обновление GT New Horizons и установка с нуля из официальных источников.
Готовая Linux-сборка запускается как `./gtnh-updater` или `Update-GTNH.sh`; Windows 10/11 — готовый `GTNH-Updater.exe`, Windows 7 — `GTNH-Updater-Win7.exe`.
Готовые Linux/Windows-сборки содержат интерпретатор; устанавливать Python, PowerShell 7, WSL или Git Bash не требуется.
Linux-бинарник x64 требует glibc 2.36+ (например, Debian 12 / Ubuntu 24.04).
При запуске **из исходников** нужен Python 3.8+; внешних Python-пакетов нет.
Готовые сборки доступны в [Releases](https://github.com/Vaneyk1973/GTNH-Updater/releases).
При скачивании отдельного EXE сохраните рядом `GTNH-Updater-licenses.zip`;
полные архивы уже содержат все лицензии.

## Использование

Двойной щелчок по EXE открывает текстовое меню. В Linux:

```bash
./Update-GTNH.sh configure
./Update-GTNH.sh status
./Update-GTNH.sh check
./Update-GTNH.sh changelog
./Update-GTNH.sh preview
./Update-GTNH.sh update
./Update-GTNH.sh rollback
```

Windows принимает те же команды:

```bat
GTNH-Updater.exe configure
GTNH-Updater.exe preview --target client
GTNH-Updater.exe update --target client
GTNH-Updater.exe rollback --target client
```

Закройте игру и сервер перед изменением файлов. Программа проверяет процессы Java,
получает блокировку, распаковывает и проверяет полный официальный архив, затем делает
полную TAR-копию инстанса, включая скрытую `.minecraft` и миры. Если заменить файлы не
удалось, возвращает предыдущие управляемые файлы. Команда `rollback` восстанавливает
также Prism libraries, patches и mmc-pack.json. Если питание/процесс оборвались,
`status` сообщает о незавершённой операции: выполните `rollback` перед запуском игры.
Миры после обновления могут содержать изменения нового мода; такой мир возвращайте
из полной резервной копии, а не только командой отката модов.

По умолчанию обновляются оба настроенных инстанса; `--target client` или `server`
выбирает один. Путь клиента можно указать как каталог Prism-инстанса или `.minecraft`.
`--path` переопределяет путь для одного запуска. `--channel daily|stable` выбирает канал;
`--version` — точную версию. Daily нельзя считать стабильным релизом.
Java должна соответствовать выбранному архиву: `--java java17` (17–26) либо `java8`.
Движок не заменяет установленную в существующем инстансе Java.

Профиль: `gtnh-updater.json`. При первом запуске читается старый Bash-профиль либо
`gtnh-updater-config.json`, если новый ещё не создан. Можно указать `--config FILE`.
Пример — `gtnh-updater.example.json`. Старый профиль не перезаписывается.
`CustomClientMods` / `CustomServerMods` сохраняют дополнительные JAR; конфликты ID
останавливают обновление. `OverrideClientMods` / `OverrideServerMods` заменяют
официальный мод с тем же ID. `ConfigPatches` применяются только при однозначном ключе.
Карты JourneyMap, закладки NEI и перечисленные пользовательские настройки сохраняются;
остальные конфиги берутся из нового пакета. `saves`, `world`, resourcepacks, options.txt
и содержимое вне управляемых каталогов не заменяются.
Дополнительные моды, не перечисленные в профиле, удаляются при обновлении;
их можно восстановить из полной резервной копии.

## Чистая установка

```bash
./Update-GTNH.sh clean-install --destination "/games/New GTNH" --channel daily
```

```bat
GTNH-Updater.exe clean-install --destination "D:\Games\New GTNH" --channel daily
```

Каталог назначения **не должен существовать**. Установка готовится рядом с ним и
появляется по завершении. Уже установленные Prism, GTNH и профиль не изменяются.
Внутри новой установки находятся portable Prism, отдельные данные лаунчера,
инстанс GTNH и собственный `gtnh-updater.json`. Запускайте `Start-Prism.cmd` или
`Start-Prism.sh`. После установки обновлять этот инстанс можно так:

```bat
GTNH-Updater.exe update --config "D:\Games\New GTNH\gtnh-updater.json" --target client
```

Windows 10/11 x64 получают актуальный официальный portable Prism MinGW.
Linux x86_64/aarch64 получает официальный AppImage (без требования FUSE).
В этих версиях Prism сам предлагает загрузку подходящей Java.
Для Windows 7 SP1 x64 требуется [KB3063858](https://www.microsoft.com/en-us/download/details.aspx?id=47442)
(либо эквивалентное обновление с AddDllDirectory) и VC++ 2015–2019 Runtime x86 для 32-битного Prism.
На чистой SP1 без обновления встроенный Python 3.8 не загружается.
Windows 7 использует последний совместимый Prism 7.2 Qt5, официальный GTNH
Java 8 и Temurin 8. При первом запуске Start-Prism устанавливает официальный VC++ 2019
Redistributable, необходимый этой сборке Prism, включая Universal CRT (KB2999226).
Если установщик требует перезагрузку, обёртка сообщает об этом: перезагрузите Windows
и повторно откройте Start-Prism.cmd. Windows 7 и Prism 7.2 уже не
поддерживаются их разработчиками; работоспособность авторизации и загрузок может
меняться. Результаты реальных VM-проверок записываются отдельно в отчёт.

`--target server` создаёт сервер и локальную Temurin Java; `--target both` — оба.
`Start-Server.cmd` / `.sh` выбирает локальную Java. EULA автоматически не принимается.
Для входа в Minecraft нужен ваш легальный аккаунт; апдейтер не собирает пароли.
Для текущего GTNH нужен рабочий видеодрайвер с OpenGL 3.3 core или выше.
Стандартный VGA-драйвер Windows в виртуальной машине для игры недостаточен.

## Источники и проверка

* GTNH daily: https://github.com/GTNewHorizons/GTNH-Daily-Builds/releases
* GTNH stable: https://www.gtnewhorizons.com/version-history/
* Prism: https://github.com/PrismLauncher/PrismLauncher/releases
* Java: https://adoptium.net/ (API и официальные GitHub-релизы Temurin)
* VC++ для старого Prism: https://aka.ms/vs/16/release/vc_redist.x86.exe

Скачивание идёт по HTTPS с проверкой встроенным Mozilla CA-бандлом;
системное хранилище сертификатов не меняется. CA-бандл имеет MPL 2.0 (LICENSES). SHA256 сверяется, если опубликован upstream.
ZIP/JAR проверяются на CRC, выход из каталога, симлинки, конфликт имён Windows,
дубликаты mod ID, наличие GregTech и необходимых файлов запуска.
`--archive FILE --version VERSION --target client|server` позволяет проверить или
установить заранее скачанный официальный ZIP; SHA256 такого файла фиксируется,
но происхождение локального файла определяет пользователь.

## Разработка и сборка

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Для сборки современного Windows EXE используйте Windows, Python 3.13,
`python -m pip install -r tools/build-requirements.txt`, затем
`tools\build-windows.cmd`. Для Win7 нужны Python 3.8, файл
`tools/build-requirements-win7.txt` и `tools\build-windows.cmd --legacy`. Сборку нужно проверять на самой старой целевой системе;
сборка на новой Windows сама по себе совместимость с Win7 не доказывает.
Linux: `python3 -m pip install pyinstaller==6.16.0 pyinstaller-hooks-contrib==2025.9`,
затем `bash tools/build-linux.sh`. Собирайте на самой старой целевой glibc.

Исходный код приложения — MIT; готовый EXE содержит Python (PSF) и bootloader
PyInstaller (GPL с исключением для распространяемых приложений). Их лицензии
должны поставляться рядом с бинарной сборкой. Скачиваемые Prism, Java, Minecraft
и моды сохраняют собственные лицензии и не включаются в лицензию MIT апдейтера.

Старые PowerShell-исходники удалены из рабочего дерева. Исходный MIT copyright
сохранён; происхождение описано в NOTICE. Старые коммиты сохранены локально;
публичная история начинается с новой кросс-платформенной версии. Репозиторий не является
официальным продуктом GTNH, Prism Launcher или Mojang/Microsoft.
