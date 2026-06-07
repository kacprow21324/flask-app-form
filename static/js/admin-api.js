(function () {
    "use strict";

    var manager = document.getElementById("api-student-manager");
    if (!manager) return;

    var form = document.getElementById("apiStudentForm");
    var studentId = document.getElementById("apiStudentId");
    var firstName = document.getElementById("apiFirstName");
    var lastName = document.getElementById("apiLastName");
    var albumNumber = document.getElementById("apiAlbumNumber");
    var email = document.getElementById("apiEmail");
    var saveButton = document.getElementById("apiSaveStudent");
    var cancelButton = document.getElementById("apiCancelEdit");
    var reloadButton = document.getElementById("apiReloadStudents");
    var statusBox = document.getElementById("apiStudentStatus");
    var studentsBody = document.getElementById("apiStudentsBody");
    var httpLog = document.getElementById("apiHttpLog");
    var csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = "api-manager-status";
        if (type) statusBox.classList.add("is-" + type);
    }

    function logRequest(method, path, status, message) {
        var row = document.createElement("div");
        row.className = "api-http-log-entry";

        var methodCell = document.createElement("span");
        methodCell.className = "api-http-method";
        methodCell.textContent = method;

        var statusCell = document.createElement("span");
        statusCell.className = "api-http-status";
        statusCell.textContent = String(status);
        statusCell.classList.add(
            Number(status) >= 200 && Number(status) < 400
                ? "is-success"
                : "is-error"
        );

        var pathCell = document.createElement("span");
        pathCell.textContent = path;

        var messageCell = document.createElement("span");
        messageCell.className = "api-http-message";
        messageCell.textContent = message || "";

        row.append(methodCell, statusCell, pathCell, messageCell);
        httpLog.prepend(row);
    }

    function responseMessage(payload, fallback) {
        if (!payload) return fallback;
        if (payload.error) {
            var details = payload.details
                ? " " + Object.values(payload.details).join(" ")
                : "";
            return payload.error + details;
        }
        return fallback;
    }

    async function apiRequest(path, options) {
        options = options || {};
        var method = options.method || "GET";
        var headers = Object.assign(
            {"Accept": "application/json"},
            options.headers || {}
        );
        if (method !== "GET" && method !== "HEAD") {
            headers["X-CSRF-Token"] = csrfToken;
        }
        try {
            var response = await fetch(path, Object.assign({}, options, {
                method: method,
                headers: headers
            }));
            var text = await response.text();
            var payload = null;
            if (text) {
                try {
                    payload = JSON.parse(text);
                } catch (_error) {
                    payload = {error: text};
                }
            }
            var message = responseMessage(
                payload,
                response.statusText || "Odpowiedź bez treści"
            );
            logRequest(method, path, response.status, message);
            if (!response.ok) {
                var apiError = new Error(message);
                apiError.status = response.status;
                apiError.payload = payload;
                throw apiError;
            }
            return payload;
        } catch (error) {
            if (!error.status) {
                logRequest(method, path, "SIEĆ", "Brak połączenia z API.");
                error = new Error("Brak połączenia z API. Spróbuj ponownie.");
                error.status = "SIEĆ";
            }
            throw error;
        }
    }

    function actionButton(label, className, handler) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = className;
        button.textContent = label;
        button.addEventListener("click", handler);
        return button;
    }

    function resetForm() {
        form.reset();
        studentId.value = "";
        saveButton.textContent = "Dodaj przez POST";
        cancelButton.hidden = true;
        firstName.focus();
    }

    function startEdit(student) {
        studentId.value = student.id;
        firstName.value = student.first_name;
        lastName.value = student.last_name;
        albumNumber.value = student.album_number;
        email.value = student.email;
        saveButton.textContent = "Zapisz przez PUT";
        cancelButton.hidden = false;
        setStatus("Edycja studenta ID " + student.id + ".", null);
        form.scrollIntoView({behavior: "smooth", block: "center"});
        firstName.focus();
    }

    async function removeStudent(student) {
        if (!window.confirm(
            "Dezaktywować studenta " + student.first_name + " " +
            student.last_name + " przez DELETE?"
        )) return;
        try {
            setStatus("Wysyłanie DELETE...", null);
            await apiRequest("/api/students/" + student.id, {method: "DELETE"});
            setStatus("Student został dezaktywowany przez API.", "success");
            if (studentId.value === String(student.id)) resetForm();
            await loadStudents(false);
        } catch (error) {
            setStatus(error.message, "error");
        }
    }

    function renderStudents(students) {
        studentsBody.replaceChildren();
        if (!students.length) {
            var emptyRow = document.createElement("tr");
            var emptyCell = document.createElement("td");
            emptyCell.colSpan = 4;
            emptyCell.textContent = "Brak aktywnych studentów.";
            emptyRow.appendChild(emptyCell);
            studentsBody.appendChild(emptyRow);
            return;
        }
        students.forEach(function (student) {
            var row = document.createElement("tr");
            row.dataset.studentId = student.id;

            var nameCell = document.createElement("td");
            nameCell.textContent = student.first_name + " " + student.last_name;
            var albumCell = document.createElement("td");
            albumCell.textContent = student.album_number;
            var emailCell = document.createElement("td");
            emailCell.textContent = student.email;
            var actionCell = document.createElement("td");
            actionCell.className = "admin-actions";
            actionCell.append(
                actionButton("Edytuj PUT", "btn btn-sm btn-secondary", function () {
                    startEdit(student);
                }),
                actionButton("Usuń DELETE", "btn btn-sm btn-danger", function () {
                    removeStudent(student);
                })
            );
            row.append(nameCell, albumCell, emailCell, actionCell);
            studentsBody.appendChild(row);
        });
    }

    async function loadStudents(showLoading) {
        if (showLoading !== false) setStatus("Pobieranie studentów przez GET...", null);
        try {
            var payload = await apiRequest("/api/students");
            renderStudents(payload.students || []);
            setStatus(
                "Pobrano " + (payload.students || []).length +
                " aktywnych studentów.",
                "success"
            );
        } catch (error) {
            studentsBody.innerHTML = '<tr><td colspan="4">Nie udało się pobrać danych.</td></tr>';
            setStatus(error.message, "error");
        }
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (!form.reportValidity()) return;
        var payload = {
            first_name: firstName.value.trim(),
            last_name: lastName.value.trim(),
            album_number: albumNumber.value.trim(),
            email: email.value.trim()
        };
        var editing = Boolean(studentId.value);
        var path = editing
            ? "/api/students/" + studentId.value
            : "/api/students";
        var method = editing ? "PUT" : "POST";
        try {
            setStatus("Wysyłanie " + method + "...", null);
            await apiRequest(path, {
                method: method,
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
            });
            setStatus(
                editing
                    ? "Dane studenta zostały zaktualizowane."
                    : "Student został dodany przez API.",
                "success"
            );
            resetForm();
            await loadStudents(false);
        } catch (error) {
            setStatus(error.message, "error");
        }
    });

    cancelButton.addEventListener("click", resetForm);
    reloadButton.addEventListener("click", function () {
        loadStudents(true);
    });
    document.getElementById("apiClearLog").addEventListener("click", function () {
        httpLog.replaceChildren();
    });

    loadStudents(true);
}());
