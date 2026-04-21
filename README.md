<div align="center">
    <h1>Flask App Form</h1>
    <p><strong>System cyfrowego obiegu dokumentacji praktyk zawodowych</strong></p>
    <p>
        <a href="documentation/dokumentacja.pdf"><strong>Przejdź do dokumentacji PDF</strong></a>
    </p>
</div>

---

## O Projekcie

Flask App Form odwzorowuje pełny cykl dokumentowania praktyk studenckich w jednej aplikacji webowej. Projekt został przygotowany tak, aby zastąpić tradycyjny obieg papierowy procesem cyfrowym, przejrzystym i łatwym do monitorowania przez wszystkie role zaangażowane w realizację praktyki.

Rozwiązanie obejmuje tworzenie i edycję dziennika praktyk, przekazanie dokumentów do wieloetapowej weryfikacji, obsługę uwag i poprawek, wystawianie ocen cząstkowych oraz finalnych, a następnie generowanie dokumentów PDF gotowych do archiwizacji.

Model procesu i logika aplikacji zostały opracowane na podstawie dokumentacji analitycznej zapisanej w pliku `dokumentacja.pdf`, z zachowaniem rzeczywistego workflow ról: Student, Opiekun Zakładowy (ZOPZ), Opiekun Uczelniany (UOPZ), Dziekanat.

---

## Zakres Funkcjonalny

| Obszar | Opis |
| :--- | :--- |
| **Dziennik praktyk** | Tworzenie wpisów dziennych, powiązanie z efektami uczenia się, kontrola statusu wpisów. |
| **Workflow i statusy** | Przejścia między SZKIC, WYSŁANY, ODRZUCONY, ZATWIERDZONY_ZOPZ, DO_POPRAWY_UOPZ, ZATWIERDZONY, ZARCHIWIZOWANY. |
| **Weryfikacja i oceny** | Ocena merytoryczna wpisów, uwagi opiekunów, wystawianie oceny Z oraz obliczanie oceny końcowej K. |
| **PDF i archiwizacja** | Generowanie dokumentów zgodnych z załącznikami oraz przekazanie do archiwum dziekanatu. |
| **Panel zbiorczy** | Widoki administracyjne dla monitorowania statusów, raportowania i obsługi dokumentacji. |

---

## Diagramy Systemowe (PNG)

### 1. Sequence - Proces weryfikacji dziennika
![Diagram 1 - Sequence Diary Verification](documentation/diagrams/diagrams_png/1.png)

### 2. State - Cykl życia dokumentu
![Diagram 2 - State Document Lifecycle](documentation/diagrams/diagrams_png/2.png)

### 3. Flow - RBAC i logika uprawnień
![Diagram 3 - RBAC Permissions](documentation/diagrams/diagrams_png/3.png)

### 4. Flow - Interfejs i nawigacja UI
![Diagram 4 - UI Navigation](documentation/diagrams/diagrams_png/4.png)

### 5. Flow - Logika walidacji wpisu
![Diagram 5 - Business Logic Validation](documentation/diagrams/diagrams_png/5.png)

### 6. Flow - Algorytm oceny końcowej
![Diagram 6 - Final Grade Algorithm](documentation/diagrams/diagrams_png/6.png)

### 7. Flow - Generowanie PDF i archiwizacja
![Diagram 7 - PDF Generation](documentation/diagrams/diagrams_png/7.png)

---
