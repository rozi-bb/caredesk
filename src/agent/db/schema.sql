-- Operational database for Evergreen Care Home (synthetic data).
-- Dates are ISO text: 'YYYY-MM-DD' for days, 'YYYY-MM-DDTHH:MM' for moments.

CREATE TABLE residents (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL,
    room        TEXT NOT NULL UNIQUE,
    care_level  TEXT NOT NULL CHECK (care_level IN ('independent', 'assisted', 'memory_care')),
    admitted_on TEXT NOT NULL
);

CREATE TABLE staff (
    id        INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    job_title TEXT NOT NULL CHECK (job_title IN (
        'nurse', 'caregiver', 'physiotherapist',
        'activities_coordinator', 'administrator', 'manager'
    ))
);

CREATE TABLE family_members (
    id        INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone     TEXT NOT NULL,
    email     TEXT NOT NULL
);

-- Who is related to whom, and whether they may see that resident's billing.
CREATE TABLE family_links (
    resident_id      INTEGER NOT NULL REFERENCES residents (id),
    family_member_id INTEGER NOT NULL REFERENCES family_members (id),
    relationship     TEXT NOT NULL,
    can_view_billing INTEGER NOT NULL CHECK (can_view_billing IN (0, 1)),
    PRIMARY KEY (resident_id, family_member_id)
);

CREATE TABLE schedule_items (
    id            INTEGER PRIMARY KEY,
    resident_id   INTEGER NOT NULL REFERENCES residents (id),
    staff_id      INTEGER REFERENCES staff (id),
    scheduled_for TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN (
        'medication_round', 'personal_care', 'meal_assistance',
        'physiotherapy', 'appointment'
    )),
    description   TEXT NOT NULL
);

CREATE TABLE activities (
    id               INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    location         TEXT NOT NULL,
    starts_at        TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL
);

-- A visit can only exist between a resident and a family member linked to them.
CREATE TABLE visits (
    id               INTEGER PRIMARY KEY,
    resident_id      INTEGER NOT NULL,
    family_member_id INTEGER NOT NULL,
    scheduled_for    TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    FOREIGN KEY (resident_id, family_member_id)
        REFERENCES family_links (resident_id, family_member_id)
);

-- reported_by_staff_id is NULL for records created automatically (emergencies).
CREATE TABLE incidents (
    id                 INTEGER PRIMARY KEY,
    resident_id        INTEGER NOT NULL REFERENCES residents (id),
    reported_by_staff_id INTEGER REFERENCES staff (id),
    occurred_at        TEXT NOT NULL,
    category           TEXT NOT NULL CHECK (category IN (
        'fall', 'missing_belongings', 'complaint', 'behaviour', 'emergency'
    )),
    description        TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('needs_action', 'resolved'))
);

CREATE TABLE billing (
    id           INTEGER PRIMARY KEY,
    resident_id  INTEGER NOT NULL REFERENCES residents (id),
    period       TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('paid', 'unpaid', 'overdue')),
    UNIQUE (resident_id, period)
);
