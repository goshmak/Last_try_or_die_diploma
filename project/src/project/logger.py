import logging.handlers


def setup_global_logger(log_file_path="./logs/app.log", log_level=logging.DEBUG):
    # Корневой логгер
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Предотвращение дублирования логов
    if logger.hasHandlers():
        logger.handlers.clear()

    # Единый форматтер для всех файлов
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s : %(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Обработчик для записи в файл (с ротацией)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file_path,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Добавление обработчиков к корневому логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
