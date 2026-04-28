<div align="center">

    <h1>Flask App Form</h1>
    <p><strong>System cyfrowego obiegu dokumentacji praktyk zawodowych</strong></p>

    <table>
        <thead>
            <tr>
                <th>Rodzaj dokumentacji</th>
                <th>Plik</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Dokumentacja analityczna projektu</td>
                <td><a href="documentation/01_dokumentacja_analityczna.pdf"><strong>Pobierz PDF</strong></a></td>
            </tr>
            <tr>
                <td>Dokumentacja dotycząca bazy danych</td>
                <td><a href="documentation/02_dokumentacja_bazy_danych.pdf"><strong>Pobierz PDF</strong></a></td>
            </tr>
        </tbody>
    </table>

</div>

---

<div align="center">
    <h2>O Projekcie</h2>
    <p>
        Flask App Form odwzorowuje pełny cykl dokumentowania praktyk studenckich w jednej aplikacji webowej.
        Projekt został przygotowany tak, aby zastąpić tradycyjny obieg papierowy procesem cyfrowym,
        przejrzystym i łatwym do monitorowania przez wszystkie role zaangażowane w realizację praktyki.
    </p>
    <p>
        Rozwiązanie obejmuje tworzenie i edycję dziennika praktyk, przekazanie dokumentów do wieloetapowej
        weryfikacji, obsługę uwag i poprawek, wystawianie ocen cząstkowych oraz finalnych,
        a następnie generowanie dokumentów PDF gotowych do archiwizacji.
    </p>
    <p>
        Model procesu i logika aplikacji zostały opracowane na podstawie dokumentacji analitycznej
        zapisanej w pliku main(1).tex, z zachowaniem rzeczywistego workflow ról:
        Student, Opiekun Zakładowy (ZOPZ), Opiekun Uczelniany (UOPZ), Dziekanat, Administrator.
    </p>
</div>

---

<div align="center">
    <h2>Zakres Funkcjonalny</h2>
    <table>
        <thead>
            <tr>
                <th>Obszar</th>
                <th>Opis</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Dziennik praktyk</td>
                <td>Tworzenie wpisów dziennych, powiązanie z efektami uczenia się, kontrola statusu wpisów.</td>
            </tr>
            <tr>
                <td>Workflow i statusy</td>
                <td>Przejścia między SZKIC, WYŁANY, ODRZUCONY, ZATWIERDZONY_ZOPZ, DO_POPRAWY_UOPZ, ZATWIERDZONY, ZARCHIWIZOWANY.</td>
            </tr>
            <tr>
                <td>Weryfikacja i oceny</td>
                <td>Ocena merytoryczna wpisów, uwagi opiekunów, wystawianie oceny Z oraz obliczanie oceny końcowej K.</td>
            </tr>
            <tr>
                <td>PDF i archiwizacja</td>
                <td>Generowanie dokumentów zgodnych z załącznikami oraz przekazanie do archiwum dziekanatu.</td>
            </tr>
            <tr>
                <td>Panel zbiorczy</td>
                <td>Widoki administracyjne dla monitorowania statusów, raportowania i obsługi dokumentacji.</td>
            </tr>
        </tbody>
    </table>
</div>

---

<h2> Diagram bazy danych (ERD)</h2>
<div align="center">
    <img src="documentation/diagrams/diagrams_png/db_diagram.png" alt="Diagram bazy danych" width="1000" />
</div>

---

<div align="center">
    <h2>Diagramy Systemowe (PNG)</h2>
    <p>Komplet diagramów wygenerowanych na podstawie analizy systemu.</p>
</div>

<div align="center">
    <h3>1. Sequence - Proces weryfikacji dziennika</h3>
    <img src="documentation/diagrams/diagrams_png/1.png" alt="Diagram 1 - Sequence Diary Verification" width="1100" />
</div>

<div align="center">
    <h3>2. State - Cykl życia dokumentu</h3>
    <img src="documentation/diagrams/diagrams_png/2.png" alt="Diagram 2 - State Document Lifecycle" width="980" />
</div>

<div align="center">
    <h3>3. Flow - RBAC i logika uprawnień</h3>
    <img src="documentation/diagrams/diagrams_png/3.png" alt="Diagram 3 - RBAC Permissions" width="1100" />
</div>

<div align="center">
    <h3>4. Flow - Interfejs i nawigacja UI</h3>
    <img src="documentation/diagrams/diagrams_png/4.png" alt="Diagram 4 - UI Navigation" width="1080" />
</div>

<div align="center">
    <h3>5. Flow - Logika walidacji wpisu</h3>
    <img src="documentation/diagrams/diagrams_png/5.png" alt="Diagram 5 - Business Logic Validation" width="1050" />
</div>

<div align="center">
    <h3>6. Flow - Algorytm oceny końcowej</h3>
    <img src="documentation/diagrams/diagrams_png/6.png" alt="Diagram 6 - Final Grade Algorithm" width="980" />
</div>

<div align="center">
    <h3>7. Flow - Generowanie PDF i archiwizacja</h3>
    <img src="documentation/diagrams/diagrams_png/7.png" alt="Diagram 7 - PDF Generation" width="1050" />
</div>

---

<div align="center">
    <h2>Pliki Mermaid</h2>
    <table>
        <thead>
            <tr>
                <th>Nr</th>
                <th>Nazwa diagramu</th>
                <th>Plik źródłowy</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>1</td>
                <td>Sequence Diary Verification</td>
                <td>documentation/diagrams/diagrams_code/Sequence_Diary_Verification.mmd</td>
            </tr>
            <tr>
                <td>2</td>
                <td>State Document Lifecycle</td>
                <td>documentation/diagrams/diagrams_code/State_Document_Lifecycle.mmd</td>
            </tr>
            <tr>
                <td>3</td>
                <td>RBAC Permissions</td>
                <td>documentation/diagrams/diagrams_code/Flow_RBAC_Permissions.mmd</td>
            </tr>
            <tr>
                <td>4</td>
                <td>UI Navigation</td>
                <td>documentation/diagrams/diagrams_code/Flow_UI_Navigation.mmd</td>
            </tr>
            <tr>
                <td>5</td>
                <td>Business Logic Validation</td>
                <td>documentation/diagrams/diagrams_code/Flow_Business_Logic_Validation.mmd</td>
            </tr>
            <tr>
                <td>6</td>
                <td>Final Grade Algorithm</td>
                <td>documentation/diagrams/diagrams_code/Flow_Final_Grade_Algorithm.mmd</td>
            </tr>
            <tr>
                <td>7</td>
                <td>PDF Generation</td>
                <td>documentation/diagrams/diagrams_code/Flow_PDF_Generation.mmd</td>
            </tr>
        </tbody>
    </table>
</div>