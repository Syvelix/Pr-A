import asyncio, pickle, json
from hashlib import sha256
from dacite import from_dict, Config
from pathlib import Path
from dataclasses import dataclass, asdict
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton, CallbackQuery
from random import randint

TOKEN_PATH = Path('./Data/TOKEN.dat').resolve()
USERS_PATH = Path('./Data/users.json').resolve()
USERS_NAME_TO_ID_PATH = Path('./Data/user_name_to_id.json').resolve()
GROUPS_PATH = Path('./Data/groups.json').resolve()
ROOTKEYS_PATH = Path('./Data/rootkeys.json').resolve()

#Класс для хранения пользователей
@dataclass
class User:
    idd: str
    name: str
    password: str
    acc_type: str
    group: str = ''

#Класс для хранения групп
@dataclass
class Group:
    members: list[User]
    name: str
    weeks: dict[int, Week]

#Класс для хранения пар
@dataclass
class Lesson:
    name: str
    cab: str
    num: int
    teacher: str

#Класс для хранения дней недели
@dataclass
class Day:
    num: int
    name: str
    lessons: list[Lesson]

#Класс для хранения недель
@dataclass
class Week:
    num: int
    days: list[Day]

@dataclass
class RootKey:
    key: str
    type: str
    maker: str
    status: str

#Получение словаря с сохранёнными пользователями
if USERS_PATH.is_file():
    with open(USERS_PATH) as usersfile:
        usersfile = usersfile.read()
    if usersfile:
        users = json.loads(usersfile)
    else:
        users = dict()

    print(json.dumps(users, indent=4, ensure_ascii=False))
else:
    users = dict()

#Получение словаря с соответсвием id:имя_аккаунта
if USERS_NAME_TO_ID_PATH.is_file():
    with open(USERS_NAME_TO_ID_PATH) as usersfile:
        usersfile = usersfile.read()
    if usersfile:
        names_to_id = json.loads(usersfile)
    else:
        names_to_id = dict()

    print(json.dumps(users, indent=4, ensure_ascii=False))
else:
    names_to_id = dict()


week_conf = Config(cast=[int], type_hooks={dict[int, Week]: lambda data: {int(key): from_dict(Week, value, config=week_conf) for key, value in data.items()}})
#Получение списка с сохранёнными группами
if GROUPS_PATH.is_file():
    with open(GROUPS_PATH) as groupfile:
        groupfile = groupfile.read()
    if groupfile:
        groups = json.loads(groupfile)
        grouplist = []
	#Группы из словаря преобразовываются в список из объектов Group
        for group in groups:
            group = from_dict(Group, groups[group], config=week_conf)
            grouplist.append(group)
        grouplist.sort(key=lambda group: group.name)
    else:
        grouplist = []
else:
    grouplist = []

#Получение списка с ключами повышения
if ROOTKEYS_PATH.is_file():
    with open(ROOTKEYS_PATH) as rkeysfile:
        rkeysfile = rkeysfile.read()
    rootkeys = json.loads(rkeysfile)
    rootkeys = [from_dict(RootKey, data=key) for key in rootkeys]
else:
    rootkeys = []

#Словарь очередей ввода, ключи - id чатов
input_queues: dict[int, asyncio.Queue] = dict()
#Словарь активных сессий, ключи - id пользователей
active_sessions: dict[int, User] = dict()

#Получение токена
if TOKEN_PATH.is_file():
    with open(TOKEN_PATH, 'rb') as token_file:
        TOKEN = pickle.load(token_file)
else:
    TOKEN = input('Введите токен бота\t')
    with open(TOKEN_PATH, 'wb') as token_file:
        pickle.dump(TOKEN, token_file)

bot = AsyncTeleBot(TOKEN);

#Если во время выполнения команды запрашивают ещё одну
async def busy(msg):
    await bot.reply_to(msg, 'Поток уже занят другой командой')

#Красивый список групп
async def get_groups_str():
    if not grouplist:
        return

    strgroups = 'Список групп:\n\n'
    for group in grouplist:
        strgroups += f'{grouplist.index(group) + 1}. {group.name}\n'

    return strgroups

#Проверка прав
async def permcheck(msg, types:set = {'teacher', 'root'}):
    if msg.from_user.id not in active_sessions:
        return 'Вы не вошли в аккаунт'
    if active_sessions[msg.from_user.id].acc_type not in types:
        return 'Недостаточно прав'

#Проверяет занято ли имя
async def is_taken(value, array):
    return value in array

#Если введён неверный аргмуент
async def wrong_arg(msg, value, pos):
    await bot.send_message(msg.chat.id, f'Неверный аргумент {value} на позиции {pos}')

#Если недостаточно аргументов
async def few_args(msg):
    await bot.send_message(msg.chat.id, 'Недостаточно аргументов')

#Сохранение групп как json
async def save_grps():
    grdict = dict()
    for gp in grouplist:
        grdict[gp.name] = asdict(gp)
    with open(GROUPS_PATH, 'w') as groupfile:
        groupfile.write(json.dumps(grdict, indent=4, ensure_ascii=False))

#Сохранение пользователей как json
async def save_usr(user:User = None, msg:Message = None, newvalue = None, vtype:str = None, kick=True):
    if user != None:
        global names_to_id, active_sessions, users
        del names_to_id[user.name]
        del active_sessions[msg.from_user.id]
        del users[str(msg.from_user.id)]
        if vtype == 'name':
            user.name = newvalue
        elif vtype == 'password':
            hashword = sha256(newvalue.encode('utf-8'))
            user.password = hashword.hexdigest()
        elif vtype == 'acc_type':
            user.acc_type = newvalue
 
        users[str(msg.from_user.id)] = asdict(user)
        names_to_id[user.name] = str(msg.from_user.id)
        if not kick:
            active_sessions[msg.from_user.id] = user

    with open(USERS_PATH, 'w') as usersfile:
            usersfile.write(json.dumps(users, indent=4, ensure_ascii=False))
    with open(USERS_NAME_TO_ID_PATH, 'w') as usersfile:
            usersfile.write(json.dumps(names_to_id, indent=4, ensure_ascii=False))

async def save_rkeys():
    with open(ROOTKEYS_PATH, 'w') as rkeysfile:
        to_save = [asdict(key) for key in rootkeys]
        rkeysfile.write(json.dumps(to_save, indent=4, ensure_ascii=False))

#Генерирует пустую неделю
async def empty_week(num:int):
    return Week(num, 
                [
                    Day(1, 'Понедельник', []),
                    Day(2, 'Вторник', []),
                    Day(3, 'Среда', []),
                    Day(4, 'Четверг', [],),
                    Day(5, 'Пятница', []),
                    Day(6, 'Суббота', [])
                ])

#Красивая строка с расписанием нндели
async def get_week_str(week:Week):
    str_week = f'Неделя No. {week.num}\n'
    for day in week.days:
        str_week += f'\n{day.name}:\n'
        for lesson in day.lessons:
            str_week += f'{lesson.num}. {lesson.name}, {lesson.cab} у {lesson.teacher}\n'
    return str_week

#Красивый список номеров учебных недель
async def get_weeks_str(group:Group):
    str_weeks = f'Номера учебных недель группы {group.name}:\n\n'
    for week in sorted(group.weeks.values(), key=lambda week: week.num):
        str_weeks += f'{week.num}.\n'
    return str_weeks

#Управление неделями
async def week_manage(msg:Message, group:Group, act:str, queue:asyncio.Queue):
    global grouplist

    match act:
	#a значит add. Добавляет пустую неделю в группу, возвращает группу
        case 'a':
            wnum = max(group.weeks.keys(), default=0) + 1
            group.weeks[wnum] = await empty_week(wnum)
            await bot.send_message(msg.chat.id, 'Добавлена пустая неделя')
            return group
        #Показать количество недель
        case 'l':
            if not group.weeks:
                return await bot.send_message(msg.chat.id, 'Расписание для группы отсутствует')
            
            await bot.send_message(msg.chat.id, f'В группе есть {len(group.weeks)} неделя(ь)(и) с расписанием')
            return await bot.send_message(msg.chat.id, await get_weeks_str(group))
        #Просмотр расписания недели
        case 's':
            if not group.weeks:
                return await bot.send_message(msg.chat.id, 'Расписание для группы отсутствует')

            await bot.send_message(msg.chat.id, await get_weeks_str(group))
            await bot.send_message(msg.chat.id, 'Введите номер недели для просмотра')
            #Вводится номер
            wnum = await queue.get()
            try: 
                wnum = int(wnum)
            except ValueError:
                return await wrong_arg(msg, wnum, 1)
	        #Он должен быть корректным номером недели
            if wnum not in group.weeks:
                return await wrong_arg(msg, wnum, 1)
            
            schedule = await get_week_str(group.weeks[wnum])
            return await bot.send_message(msg.chat.id, schedule)
        #e значит edit
        case 'e':
            if not group.weeks:
                return await bot.send_message(msg.chat.id, 'Расписание для группы отсутствует')
            
            await bot.send_message(msg.chat.id, await get_weeks_str(group))
            await bot.send_message(msg.chat.id, 'Введите действие над неделей')
            line = await queue.get()
            line = line.split(' ')
            line = list(reversed(line))

            #Первый аргумент должен быть номером недели в списке group.weeks
            try: 
                wnum = int(line[-1])
            except ValueError:
                return await wrong_arg(msg, line[-1], 1)
            #Он должен быть корректным номером недели
            if wnum not in group.weeks:
                print(wnum, group.weeks)
                return await wrong_arg(msg, line[-1], 1)
            line.pop()
            #Если кроме номера недели ничего не передали, то аргументов недостаточно
            if not line:
                return await few_args(msg)
            week = group.weeks[wnum]

            #Второй аргумент - действие над неделей
            act = line[-1]
            match act:
                #n значит num
                case 'n':
                    await bot.send_message(msg.chat.id, 'Введите новый номер недели')
                    num = await queue.get()
                    try:
                        num = int(num)
                    except ValueError:
                        return await wrong_arg(msg, num, 2)
                    week.num = int(num)
                    group.weeks[wnum] = week
                    await bot.send_message(msg.chat.id, 'Номер недели изменён')
                    return group
                #d значит delete
                case 'd':
                    del group.weeks[wnum]
                    await bot.send_message(msg.chat.id, f'Неделя {wnum} удалена')
                    return group
                case _:
                    return await wrong_arg(msg, act, 2)
        case _:
            return await wrong_arg(msg, act, 3)         

#Команда start/help
@bot.message_handler(commands=['start', 'help'])
async def start(msg:Message):
    await bot.send_message(msg.chat.id, "Я есть!")

#Команда регистрации
@bot.message_handler(commands=['reg'])
async def reg(msg:Message):
    global users, names_to_id, active_sessions, input_queues
    if msg.chat.id in input_queues:
        return await busy(msg)
    if msg.from_user.id in active_sessions:
        return await bot.send_message(msg.chat.id, 'Сначала нужно выйти из аккаунта')
    if str(msg.from_user.id) in users and ' force' not in msg.text:
        return await bot.send_message(msg.chat.id, 'К вашему id уже привязан аккаунт Чтобы его пересоздать, используйте\n /reg force')

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        await bot.send_message(msg.chat.id, "Регистрация")

        await bot.send_message(msg.chat.id, "Введите имя")
        name = await queue.get()
        if await is_taken(name, names_to_id):
            return await bot.send_message(msg.chat.id, 'Имя уже занято')

        await bot.send_message(msg.chat.id, "Введите пароль")
        password = await queue.get()
        hashword = sha256(password.encode('utf-8'))

        if str(msg.from_user.id) in users:
            del names_to_id[from_dict(User, users[str(msg.from_user.id)]).name]

        user = User(str(msg.from_user.id), name, hashword.hexdigest(), 'normal')

        users[str(msg.from_user.id)] = asdict(user)
        
        names_to_id[name] = str(msg.from_user.id)

        await save_usr()

        await bot.reply_to(msg, "Регистрация успешна!")
        print(names_to_id)
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда входа в аккаунт
@bot.message_handler(commands=['log'])
async def log(msg:Message):
    global users, input_queues, active_sessions
    if msg.chat.id in input_queues:
        return await busy(msg)
    if msg.from_user.id in active_sessions:
        return await bot.send_message(msg.chat.id, f'Вы уже вошли как {active_sessions[msg.from_user.id].name}')
        
    
    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        await bot.send_message(msg.chat.id, 'Введите имя')
        name = await queue.get()
        if name not in names_to_id:
            await bot.send_message(msg.chat.id, 'Нет такого пользователя')
            return
        user = from_dict(User, users[names_to_id[name]])
        
        await bot.send_message(msg.chat.id, 'Введите пароль')
        password = await queue.get()
        hashword = str(sha256(password.encode('utf-8')).hexdigest())
        if hashword != user.password:
            await bot.send_message(msg.chat.id, 'Неверный пароль')
            return

        active_sessions[msg.from_user.id] = user
        print(active_sessions)
        await bot.send_message(msg.chat.id, f'Вы вошли как {active_sessions[msg.from_user.id].name}')
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда выхода из аккаунта
@bot.message_handler(commands=['unlog'])
async def unlog(msg:Message):
    global active_sessions
    if msg.from_user.id in active_sessions:
        del active_sessions[msg.from_user.id]
        await bot.send_message(msg.chat.id, 'Вы вышли из аккаунта')
    else:
        await bot.send_message(msg.chat.id, 'Вход не выполнен')
    print(active_sessions)

#Команда для удаления аккаунта
@bot.message_handler(commands=['del'])
async def acc_del(msg:Message):
    global input_queues, active_sessions
    if msg.chat.id in input_queues:
        return await busy(msg)
    if msg.from_user.id not in active_sessions:
        await bot.send_message(msg.chat.id, "Сначала войдите в аккаунт")
        return

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        await bot.send_message(msg.chat.id, 'Вы уверены? Введите "ДА" чтобы подтвердить')
        conf = await queue.get()

        if conf == 'ДА':
            user = active_sessions[msg.from_user.id]
            del active_sessions[int(user.idd)]
            del users[user.idd]
            del names_to_id[user.name]

            with open(USERS_PATH, 'w') as usersfile:
                usersfile.write(json.dumps(users, indent=4, ensure_ascii=False))
            with open(USERS_NAME_TO_ID_PATH, 'w') as usersfile:
                usersfile.write(json.dumps(names_to_id, indent=4, ensure_ascii=False))
            
            await bot.send_message(msg.chat.id, f'Аккаунт {user.name} удалён')
        else:
            await bot.send_message(msg.chat.id, 'Удаление отменено')
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

    print(users)
    print(names_to_id)
    print(active_sessions)

#Команда создания пустой группы
#Требуется тип аккаунта teacher или root
@bot.message_handler(commands=['mkgrp'])
async def mkgrp(msg:Message):
    global input_queues, grouplist
    perms = await permcheck(msg)
    if perms != None:
        await bot.send_message(msg.chat.id, perms)
        return
    if msg.chat.id in input_queues:
        return await busy(msg)

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        await bot.send_message(msg.chat.id, 'Введите &, чтобы отменить создание группы')

        await bot.send_message(msg.chat.id, 'Введите название группы')
        name = await queue.get()
        if name == "&":
            return await bot.send_message(msg.chat.id, 'Отменено')
            
        if await is_taken(name, [group.name for group in grouplist]):
            return await bot.send_message(msg.chat.id, 'Группа уже существует')

        group = Group([], name, dict())

        grouplist.append(group)
        await save_grps()

        await bot.send_message(msg.chat.id, f'Группа {group.name} создана. Используйте /manage для управления')
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда для управления группами
#Требуется тип аккаунта teacher или root
@bot.message_handler(commands=['manage'])
async def manage(msg:Message):
    global input_queues, grouplist
    perms = await permcheck(msg)
    if msg.chat.id in input_queues:
        return await busy(msg)
    if perms != None:
        await bot.send_message(msg.chat.id, perms)
        return
    
    strgroups = await get_groups_str()
    if strgroups == None:
        await bot.send_message(msg.chat.id, 'Ещё не создано ни одной группы. Используйте /mkgrp для создания')
        return

    await bot.send_message(msg.chat.id, strgroups)

    try:
        queue = asyncio.Queue()
        input_queues[msg.chat.id] = queue

        await bot.send_message(msg.chat.id, 'Введите действие над группой или & для отмены.\nДля справки используйте /manhelp')

	#Аргументы передаются одной через пробел
        line = await queue.get()
        line = line.split(' ')
	#Список разворачивается для удобства, поэтому аргументы берутся с конца списка
        line = list(reversed(line))
	#Символ & на первой позиции отменяет manage
        if line[-1] == '&':
            return await bot.send_message(msg.chat.id, 'Отменено')

	#Первый аргумент должен быть номером группы в списке grouplist
        try: 
            gnum = int(line[-1]) - 1
        except ValueError:
            return await wrong_arg(msg, line[-1], 1)
	#Он должен быть корректным номером группы
        if gnum >= len(grouplist) or gnum < 0:
            return await wrong_arg(msg, line[-1], 1)
        line.pop()
	#Если кроме номера группы ничего не передали, то аргументов недостаточно
        if not line:
            return await few_args(msg)
        group = grouplist[gnum]

	#Второй аргумент - первичное действие
        act = line[-1]

        match act:
	    #d значит delete. Удаление группы
            case 'd':
                await bot.send_message(msg.chat.id, f'Группа {grouplist[gnum].name} удалена')
                del grouplist[gnum]
                return await save_grps()
            #r значит rename. Переименование группы
            case 'r':
                await bot.send_message(msg.chat.id, 'Введите новое имя для группы')
                name = await queue.get()
                if name == '&':
                    return await bot.send_message(msg.chat.id, 'Отменено')
                if await is_taken(name, [group.name for group in grouplist]):
                    return await bot.send_message(msg.chat.id, 'Имя уже занято, отмена')
                group.name = name
                await bot.send_message(msg.chat.id, 'Группа переименована')
                return await save_grps()
	    #w значит week. Вызывается управление неделями
            case 'w':
                line.pop()
		#Если нет третьего элемента строки, то аргументов недостаточнр
                if not line:
                    return await few_args(msg)

                act = line[-1]
		#Третий аргумент передаётся в функцию управления неделями
                group = await week_manage(msg, group, act, queue)
                if not isinstance(group, Group):
                    return
                return await save_grps()

	    #В ином случае выход из manage
            case _:
                return await wrong_arg(msg, act, 2)
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда смены имени
@bot.message_handler(commands=['rename'])
async def rename(msg:Message):
    global users, names_to_id, active_sessions, input_queues
    if msg.from_user.id not in active_sessions:
        return await bot.send_message(msg.chat.id, 'Вы не вошли в аккант')
    if msg.from_user.id in input_queues:
        return await bot.send_message(msg.chat.id, 'Поток уже занят другой командой')

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue
    user = active_sessions[msg.from_user.id]
    try:
        await bot.send_message(msg.chat.id, 'Введите новое имя. & для отмены')
        name = await queue.get()
        if name == '&':
            return await bot.send_message(msg.chat.id, 'Отменено')
        await save_usr(user, msg, name, 'name')
        return await bot.send_message(msg.chat.id, 'Имя изменено. Войдите в аккаунт заново')
    finally:
        if msg.from_user.id in input_queues:
            del input_queues[msg.chat.id]

#Команда смены пароля
@bot.message_handler(commands=['repass'])
async def repass(msg:Message):
    global users, names_to_id, active_sessions, input_queues
    if msg.from_user.id not in active_sessions:
        return await bot.send_message(msg.chat.id, 'Вы не вошли в аккант')
    if msg.from_user.id in input_queues:
        return await bot.send_message(msg.chat.id, 'Поток уже занят другой командой')

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue
    user = active_sessions[msg.from_user.id]

    try:
        await bot.send_message(msg.chat.id, 'Введите новый пароль. & для отмены')
        password = await queue.get()
        if password == '&':
            return await bot.send_message(msg.chat.id, 'Отменено')

        await save_usr(user, msg, password, 'password')
        return await bot.send_message(msg.chat.id, 'Пароль изменён. Войдите в аккаунт заново')
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда для создания ключей повышения
#Доступна только для root-аккаунтов
@bot.message_handler(commands=['rootkey'])
async def rootkey(msg:Message):
    global rootkeys, input_queues
    if msg.chat.id in input_queues:
        return await busy(msg)
    perms = await permcheck(msg, {'root'})
    if perms != None:
        return await bot.send_message(msg.chat.id, perms)

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        await bot.send_message(msg.chat.id, 'Введите команду\nadd - создать ключ\noff - отключить ключ')
        act = await queue.get()

        match act:
            #Создание ключа
            case 'add':
                rkey = str(randint(0, 28918928919228291923))
                while rkey in [key.key for key in rootkeys]:
                    rkey = str(randint(0, 28918928919228291923))

                ktype = ''
                while ktype not in {'1', '2', '&'}:
                    await bot.send_message(msg.chat.id, 'Выберите тип ключа\n1. root (полный доступ)\n2. teacher (доступ к неделям и группам)\n\n& - отмена')
                    ktype = await queue.get()
                if ktype == '&':
                    return await bot.send_message(msg.chat.id, 'Отменено')

                kboard = InlineKeyboardMarkup()
                kboard.add(InlineKeyboardButton(text="Скопировать", copy_text=CopyTextButton(rkey)))

                await bot.send_message(msg.chat.id, f'Ключ создан: ||{rkey}||', parse_mode='MarkdownV2', reply_markup=kboard)
                rkey = sha256(rkey.encode('utf-8'))

                match ktype:
                    #Ключ с полным доступом
                    case '1':
                        rkey = RootKey(rkey.hexdigest(), 'root', active_sessions[msg.from_user.id].name, 'active')
                    #Ключ с доступом учителя
                    case '2':
                        rkey = RootKey(rkey.hexdigest(), 'teacher', active_sessions[msg.from_user.id].name, 'active')
                rootkeys.append(rkey)
            #Отключение ключа
            case 'off':
                if not rootkeys:
                    return await bot.send_message(msg.chat.id, 'Ключи повышения отсутствуют')

                await bot.send_message(msg.chat.id, 'Введите ключ для отключения')
                rkey = await queue.get()
                rkey = sha256(rkey.encode('utf-8')).hexdigest()

                rkeys = [rkey.key for rkey in rootkeys]
                if rkey not in rkeys:
                    return await bot.send_message(msg.chat.id, "Недействительный ключ")
                
                rkey = [key for key in rootkeys if key.key == rkey][0]

                if rkey.status == 'disabled':
                    return await bot.send_message(msg.chat.id, 'Ключ уже был отключён')
                
                nrkey = rkey
                nrkey.status = 'disabled'
                rootkeys[rootkeys.index(rkey)] = nrkey
                await bot.send_message(msg.chat.id, 'Ключ отключён')
            case _:
                return await wrong_arg(msg, act, 1)
        await save_rkeys()
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]

#Команда повышения аккаунта
@bot.message_handler(commands=['boost'])
async def boost(msg:Message):
    global rootkeys, input_queues
    if msg.from_user.id not in active_sessions:
        return await bot.send_message(msg.chat.id, 'Вы не вошли в аккаунт')
    if msg.chat.id in input_queues:
        return await busy(msg)

    rkeys = [rkey.key for rkey in rootkeys]

    queue = asyncio.Queue()
    input_queues[msg.chat.id] = queue

    try:
        user = active_sessions[msg.from_user.id]
        if user.acc_type == 'root':
            return await bot.send_message(msg.chat.id, 'Вы уже root!')

        await bot.send_message(msg.chat.id, 'Введите ключ повышения')
        rkey = await queue.get()
        rkey = sha256(rkey.encode('utf-8')).hexdigest()

        if rkey not in rkeys:
            return await bot.send_message(msg.chat.id, 'Недействительный ключ')

        rootkey = [key for key in rootkeys if key.key == rkey][0]
        if rootkey.status == 'disabled':
            return await bot.send_message(msg.chat.id, 'Ключ отключён. Возможно уже был активирован кем-то ещё')
        nrootkey = rootkey
        nrootkey.status = 'disabled'
        rootkeys[rootkeys.index(rootkey)] = nrootkey

        await save_usr(user, msg, rootkey.type, 'acc_type', kick = False)
        await save_rkeys()
        user = active_sessions[msg.from_user.id]
        await bot.send_message(msg.chat.id, f'Тип аккаунта изменён на {user.acc_type}')
    finally:
        if msg.chat.id in input_queues:
            del input_queues[msg.chat.id]


#Получение любого ввода, не являющегося определённой команды
@bot.message_handler(func=lambda msg: msg.text != None and not msg.text.startswith('/'))
async def on_message(msg:Message):
    global input_queues
    if msg.chat.id in input_queues:
        await input_queues[msg.chat.id].put(msg.text)

print('Starting now!')
asyncio.run(bot.infinity_polling())
