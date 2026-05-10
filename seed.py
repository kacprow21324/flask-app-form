"""
Uruchom raz, żeby wypełnić bazę użytkownikami testowymi i efektami:
  python seed.py
"""
from werkzeug.security import generate_password_hash
from app import app
from models import db, User, LearningEffect


USERS = [
    {
        "email": "student@student.ans-elblag.pl",
        "password": "Student123!",
        "first_name": "Student",
        "last_name": "Testowy",
        "role": "student",
        "is_active": 1,
    },
    {
        "email": "opiekun@ans-elblag.pl",
        "password": "Opiekun123!",
        "first_name": "Opiekun",
        "last_name": "Testowy",
        "role": "uopz",
        "is_active": 1,
    },
    {
        "email": "admin@ans-elblag.pl",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "Systemu",
        "role": "admin",
        "is_active": 1,
    },
]

EFFECTS = [
    (1, "Ma wiedzę na temat sposobu realizacji zadań inżynierskich dotyczących informatyki z zachowaniem standardów i norm technicznych"),
    (2, "Zna technologie, narzędzia, metody, techniki oraz sprzęt stosowane w informatyce"),
    (3, "Zna ekonomiczne, prawne skutki własnych działań podejmowanych w ramach praktyki oraz ograniczenia wynikające z prawa autorskiego i kodeksu pracy"),
    (4, "Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka"),
    (5, "Pozyskuje informacje odnośnie technologii, metod, technik, sprzętu wymaganego do realizacji powierzonego zadania, posługując się rozmaitymi źródłami literaturowymi i zasobami publikowanymi w języku polskim jak i angielskim"),
    (6, "W oparciu o kontakty ze środowiskiem inżynierskim zakładu, potrafi podnieść swoje kompetencje, wiedzę i umiejętności, co najmniej z dwóch zakresów: zadania dotyczące sprzętu i oprogramowania: np.: programowania, administrowanie siecią komputerową, konserwacja sprzętu i oprogramowania, bieżące usuwanie usterek, administrowanie zasobami informatycznymi, zakładu pracy / instytucji, (e)-usługami."),
    (7, "Opracowuje dokumentację dotyczącą realizacji podejmowanych zadań w ramach praktyki, a także referuje ustnie prezentowane w niej zagadnienia"),
    (8, "Potrafi zidentyfikować problem informatyczny występujący w zakładzie pracy / instytucji, opisać go, przedstawić koncepcję rozwiązania i ją zrealizować."),
    (9, "Potrafi rozwiązać rzeczywiste zadanie inżynierskie z zakresu działalności informatycznej zakładu pracy/instytucji stosując normy i standardy stosowane w informatyce oraz biorąc pod uwagę aspekty środowiskowe i etyczne."),
    (10, "Pracuje w zespole zajmującym się zawodowo branżą IT"),
    (11, "Przestrzega zasad etyki zawodowej i zgodnie z tymi zasadami korzysta z wiedzy i pomocy doświadczonych kolegów"),
    (12, "Kontaktując się z osobami spoza branży potrafi zarówno pozyskać od nich niezbędne informacje do realizacji planowanego zadania, jak i przekazać im w sposób zrozumiały informacje i opinie z zakresu informatyki"),
    (13, "Dostrzega w praktyce tempo deaktualizacji wiedzy informatycznej oraz skutki działalności informatyków w szczególności ekonomiczne i społeczne"),
]


with app.app_context():
    db.create_all()

    added_users = 0
    for data in USERS:
        if User.query.filter_by(email=data["email"]).first():
            print(f"  pomijam (istnieje): {data['email']}")
            continue
        user = User(
            email=data["email"],
            password_hash=generate_password_hash(data["password"]),
            first_name=data["first_name"],
            last_name=data["last_name"],
            role=data["role"],
            is_active=data["is_active"],
            email_verified=1,
        )
        db.session.add(user)
        added_users += 1
        print(f"  dodano: {data['email']}  hasło: {data['password']}")

    added_effects = 0
    for nr, opis in EFFECTS:
        if LearningEffect.query.filter_by(nr=nr).first():
            continue
        db.session.add(LearningEffect(nr=nr, opis=opis))
        added_effects += 1

    db.session.commit()
    print(f"\nGotowe – dodano {added_users} użytkowników, {added_effects} efektów uczenia się.")
