import sqlite3
import os

def create_and_populate(db_path: str = "store.db") -> None:
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # 1. Artists
    cur.execute("""
    CREATE TABLE artists (
        ArtistId INTEGER PRIMARY KEY AUTOINCREMENT,
        Name NVARCHAR(120) NOT NULL
    );
    """)

    # 2. Albums
    cur.execute("""
    CREATE TABLE albums (
        AlbumId INTEGER PRIMARY KEY AUTOINCREMENT,
        Title NVARCHAR(160) NOT NULL,
        ArtistId INTEGER NOT NULL,
        FOREIGN KEY (ArtistId) REFERENCES artists (ArtistId) ON DELETE CASCADE
    );
    """)

    # 3. Media Types
    cur.execute("""
    CREATE TABLE media_types (
        MediaTypeId INTEGER PRIMARY KEY AUTOINCREMENT,
        Name NVARCHAR(120) NOT NULL
    );
    """)

    # 4. Genres
    cur.execute("""
    CREATE TABLE genres (
        GenreId INTEGER PRIMARY KEY AUTOINCREMENT,
        Name NVARCHAR(120) NOT NULL
    );
    """)

    # 5. Tracks
    cur.execute("""
    CREATE TABLE tracks (
        TrackId INTEGER PRIMARY KEY AUTOINCREMENT,
        Name NVARCHAR(200) NOT NULL,
        AlbumId INTEGER,
        MediaTypeId INTEGER NOT NULL,
        GenreId INTEGER,
        Composer NVARCHAR(220),
        Milliseconds INTEGER NOT NULL,
        Bytes INTEGER,
        UnitPrice NUMERIC(10,2) NOT NULL,
        FOREIGN KEY (AlbumId) REFERENCES albums (AlbumId),
        FOREIGN KEY (MediaTypeId) REFERENCES media_types (MediaTypeId),
        FOREIGN KEY (GenreId) REFERENCES genres (GenreId)
    );
    """)

    # 6. Playlists
    cur.execute("""
    CREATE TABLE playlists (
        PlaylistId INTEGER PRIMARY KEY AUTOINCREMENT,
        Name NVARCHAR(120) NOT NULL
    );
    """)

    # 7. Playlist Track
    cur.execute("""
    CREATE TABLE playlist_track (
        PlaylistId INTEGER NOT NULL,
        TrackId INTEGER NOT NULL,
        PRIMARY KEY (PlaylistId, TrackId),
        FOREIGN KEY (PlaylistId) REFERENCES playlists (PlaylistId),
        FOREIGN KEY (TrackId) REFERENCES tracks (TrackId)
    );
    """)

    # 8. Employees
    cur.execute("""
    CREATE TABLE employees (
        EmployeeId INTEGER PRIMARY KEY AUTOINCREMENT,
        LastName NVARCHAR(20) NOT NULL,
        FirstName NVARCHAR(20) NOT NULL,
        Title NVARCHAR(30),
        ReportsTo INTEGER,
        BirthDate DATETIME,
        HireDate DATETIME,
        Address NVARCHAR(70),
        City NVARCHAR(40),
        State NVARCHAR(40),
        Country NVARCHAR(40),
        PostalCode NVARCHAR(10),
        Phone NVARCHAR(24),
        Fax NVARCHAR(24),
        Email NVARCHAR(60),
        FOREIGN KEY (ReportsTo) REFERENCES employees (EmployeeId)
    );
    """)

    # 9. Customers
    cur.execute("""
    CREATE TABLE customers (
        CustomerId INTEGER PRIMARY KEY AUTOINCREMENT,
        FirstName NVARCHAR(40) NOT NULL,
        LastName NVARCHAR(20) NOT NULL,
        Company NVARCHAR(80),
        Address NVARCHAR(70),
        City NVARCHAR(40),
        State NVARCHAR(40),
        Country NVARCHAR(40),
        PostalCode NVARCHAR(10),
        Phone NVARCHAR(24),
        Fax NVARCHAR(24),
        Email NVARCHAR(60) NOT NULL,
        SupportRepId INTEGER,
        FOREIGN KEY (SupportRepId) REFERENCES employees (EmployeeId)
    );
    """)

    # 10. Invoices
    cur.execute("""
    CREATE TABLE invoices (
        InvoiceId INTEGER PRIMARY KEY AUTOINCREMENT,
        CustomerId INTEGER NOT NULL,
        InvoiceDate DATETIME NOT NULL,
        BillingAddress NVARCHAR(70),
        BillingCity NVARCHAR(40),
        BillingState NVARCHAR(40),
        BillingCountry NVARCHAR(40),
        BillingPostalCode NVARCHAR(10),
        Total NUMERIC(10,2) NOT NULL,
        FOREIGN KEY (CustomerId) REFERENCES customers (CustomerId)
    );
    """)

    # 11. Invoice Items
    cur.execute("""
    CREATE TABLE invoice_items (
        InvoiceLineId INTEGER PRIMARY KEY AUTOINCREMENT,
        InvoiceId INTEGER NOT NULL,
        TrackId INTEGER NOT NULL,
        UnitPrice NUMERIC(10,2) NOT NULL,
        Quantity INTEGER NOT NULL,
        FOREIGN KEY (InvoiceId) REFERENCES invoices (InvoiceId),
        FOREIGN KEY (TrackId) REFERENCES tracks (TrackId)
    );
    """)

    # Data Inserts
    media_types = [
        (1, 'MPEG audio file'),
        (2, 'Protected AAC audio file'),
        (3, 'Protected MPEG-4 video file'),
        (4, 'Purchased AAC audio file'),
        (5, 'AAC audio file')
    ]
    cur.executemany('INSERT INTO media_types (MediaTypeId, Name) VALUES (?, ?)', media_types)

    genres = [
        (1, 'Rock'), (2, 'Jazz'), (3, 'Metal'), (4, 'Alternative & Punk'),
        (5, 'Rock And Roll'), (6, 'Blues'), (7, 'Latin'), (8, 'Reggae'),
        (9, 'Pop'), (10, 'Soundtrack'), (11, 'Bossa Nova'), (12, 'Easy Listening'),
        (13, 'Heavy Metal'), (14, 'R&B/Soul'), (15, 'Electronica/Dance'),
        (16, 'World'), (17, 'Hip Hop/Rap'), (18, 'Science Fiction'), (19, 'TV Shows'),
        (20, 'Sci Fi & Fantasy'), (21, 'Drama'), (22, 'Comedy'), (23, 'Alternative'),
        (24, 'Classical'), (25, 'Opera')
    ]
    cur.executemany('INSERT INTO genres (GenreId, Name) VALUES (?, ?)', genres)

    artists = [
        (1, 'AC/DC'), (2, 'Accept'), (3, 'Aerosmith'), (4, 'Alanis Morissette'),
        (5, 'Alice In Chains'), (6, 'Antônio Carlos Jobim'), (7, 'Apocalyptica'),
        (8, 'Audioslave'), (9, 'BackBeat'), (10, 'Billy Cobham'),
        (11, 'Black Label Society'), (12, 'Black Sabbath'), (13, 'Body Count'),
        (14, 'Bruce Dickinson'), (15, 'Buddy Guy'), (16, 'Caetano Veloso'),
        (17, 'Chico Buarque'), (18, 'Chico Science & Nação Zumbi'), (19, 'Cidade Negra'),
        (20, 'Cláudio Zoli'), (21, 'Various Artists'), (22, 'Led Zeppelin'),
        (23, 'Frank Sinatra'), (24, 'Metallica'), (25, 'Queen'),
        (26, 'Pink Floyd'), (27, 'Miles Davis'), (28, 'The Beatles'),
        (29, 'Nirvana'), (30, 'Deep Purple')
    ]
    cur.executemany('INSERT INTO artists (ArtistId, Name) VALUES (?, ?)', artists)

    albums = [
        (1, 'For Those About To Rock We Salute You', 1),
        (2, 'Balls to the Wall', 2),
        (3, 'Restless and Wild', 2),
        (4, 'Let There Be Rock', 1),
        (5, 'Big Ones', 3),
        (6, 'Jagged Little Pill', 4),
        (7, 'Facelift', 5),
        (8, 'Warner 25 Anos', 6),
        (9, 'Plays Metallica By Four Cellos', 7),
        (10, 'Audioslave', 8),
        (11, 'Out of Exile', 8),
        (12, 'BackBeat Soundtrack', 9),
        (13, 'The Best Of Billy Cobham', 10),
        (14, 'Alcohol Fueled Brewtality Live! [Disc 1]', 11),
        (15, 'Alcohol Fueled Brewtality Live! [Disc 2]', 11),
        (16, 'Black Sabbath', 12),
        (17, 'Black Sabbath Vol4 (Remaster)', 12),
        (18, 'Body Count', 13),
        (19, 'Chemical Wedding', 14),
        (20, 'The Best Of Buddy Guy - The Millenium Collection', 15),
        (21, 'Led Zeppelin I', 22),
        (22, 'Led Zeppelin II', 22),
        (23, 'Led Zeppelin III', 22),
        (24, 'Led Zeppelin IV', 22),
        (25, 'Master of Puppets', 24),
        (26, 'Ride the Lightning', 24),
        (27, 'A Night at the Opera', 25),
        (28, 'The Dark Side of the Moon', 26),
        (29, 'Kind of Blue', 27),
        (30, 'Abbey Road', 28),
        (31, 'Nevermind', 29),
        (32, 'Machine Head', 30)
    ]
    cur.executemany('INSERT INTO albums (AlbumId, Title, ArtistId) VALUES (?, ?, ?)', albums)

    employees = [
        (1, 'Adams', 'Andrew', 'General Manager', None, '1962-02-18', '2016-08-14', '11120 Jasper Ave NW', 'Edmonton', 'AB', 'Canada', 'T5K 2N1', '+1 (780) 428-9482', '+1 (780) 428-3457', 'andrew@chinookcorp.com'),
        (2, 'Edwards', 'Nancy', 'Sales Manager', 1, '1958-12-08', '2016-05-01', '825 8 Ave SW', 'Calgary', 'AB', 'Canada', 'T2P 2T3', '+1 (403) 262-3443', '+1 (403) 262-3322', 'nancy@chinookcorp.com'),
        (3, 'Peacock', 'Jane', 'Sales Support Agent', 2, '1973-08-29', '2017-04-01', '1111 6 Ave SW', 'Calgary', 'AB', 'Canada', 'T2P 5M5', '+1 (403) 262-3443', '+1 (403) 262-6712', 'jane@chinookcorp.com'),
        (4, 'Park', 'Margaret', 'Sales Support Agent', 2, '1947-09-19', '2017-05-03', '683 10 Street SW', 'Calgary', 'AB', 'Canada', 'T2P 5G3', '+1 (403) 263-4423', '+1 (403) 263-4289', 'margaret@chinookcorp.com'),
        (5, 'Johnson', 'Steve', 'Sales Support Agent', 2, '1965-03-03', '2017-10-17', '7727B 41 Ave', 'Calgary', 'AB', 'Canada', 'T3B 1Y7', '1 (780) 632-6209', '1 (780) 632-6210', 'steve@chinookcorp.com'),
        (6, 'Mitchell', 'Michael', 'IT Manager', 1, '1973-07-01', '2016-10-17', '5827 Bowness Road NW', 'Calgary', 'AB', 'Canada', 'T3B 0C5', '+1 (403) 246-9887', '+1 (403) 246-9899', 'michael@chinookcorp.com'),
        (7, 'King', 'Robert', 'IT Staff', 6, '1970-05-29', '2017-01-02', '590 Columbia RD SW', 'Calgary', 'AB', 'Canada', 'T2T 5X8', '+1 (403) 456-8485', '+1 (403) 456-8486', 'robert@chinookcorp.com'),
        (8, 'Callahan', 'Laura', 'IT Staff', 6, '1968-01-09', '2017-03-04', '923 7 ST NW', 'Lethbridge', 'AB', 'Canada', 'T1H 1Y8', '+1 (403) 467-3351', '+1 (403) 467-8772', 'laura@chinookcorp.com')
    ]
    cur.executemany('INSERT INTO employees (EmployeeId, LastName, FirstName, Title, ReportsTo, BirthDate, HireDate, Address, City, State, Country, PostalCode, Phone, Fax, Email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', employees)

    customers = [
        (1, 'Luís', 'Gonçalves', 'Embraer - Empresa Brasileira de Aeronáutica S.A.', 'Av. Brigadeiro Faria Lima, 2170', 'São José dos Campos', 'SP', 'Brazil', '12227-000', '+55 (12) 3923-5555', '+55 (12) 3923-5566', 'luisg@embraer.com.br', 3),
        (2, 'Leonie', 'Köhler', None, 'Theodor-Heuss-Straße 34', 'Stuttgart', None, 'Germany', '70174', '+49 0711 2842222', None, 'leonekohler@surfeu.de', 5),
        (3, 'François', 'Tremblay', None, '1498 rue Bélanger', 'Montréal', 'QC', 'Canada', 'H2G 1A7', '+1 (514) 721-4711', None, 'ftremblay@gmail.com', 3),
        (4, 'Bjørn', 'Hansen', None, 'Ullevålsveien 14', 'Oslo', None, 'Norway', '0171', '+47 22 44 22 22', None, 'bjorn.hansen@yahoo.no', 4),
        (5, 'František', 'Wichterlová', 'Česká republika', 'Klanova 9/506', 'Prague', None, 'Czech Republic', '14700', '+420 2 4172 5555', '+420 2 4172 5555', 'frantisekw@jetbrains.com', 4),
        (6, 'Helena', 'Holý', None, 'Rilská 3174/6', 'Prague', None, 'Czech Republic', '14300', '+420 2 4177 0449', None, 'hholy@gmail.com', 5),
        (7, 'Astrid', 'Gruber', None, 'Rotenturmstraße 4, 1010 Innere Stadt', 'Vienne', None, 'Austria', '1010', '+43 01 5134505', None, 'astrid.gruber@apple.at', 5),
        (8, 'Daan', 'Peeters', None, 'Grétrystraat 63', 'Brussels', None, 'Belgium', '1000', '+32 02 219 03 03', None, 'daan_peeters@apple.be', 4),
        (9, 'Kara', 'Nielsen', None, 'Sønder Boulevard 51', 'Copenhagen', None, 'Denmark', '1720', '+453 3332 4444', None, 'kara.nielsen@jubii.dk', 4),
        (10, 'Eduardo', 'Martins', 'Woodstock Discos', 'Rua Dr. Falcão Filho, 155', 'São Paulo', 'SP', 'Brazil', '01007-010', '+55 (11) 3033-5446', '+55 (11) 3033-4564', 'eduardo@woodstock.com.br', 4),
        (11, 'Alexandre', 'Rocha', 'Banco do Brasil S.A.', 'Av. Paulista, 2022', 'São Paulo', 'SP', 'Brazil', '01310-200', '+55 (11) 3055-3278', '+55 (11) 3055-8131', 'alero@uol.com.br', 5),
        (12, 'Roberto', 'Almeida', 'Riotur', 'Praça Pio X, 119', 'Rio de Janeiro', 'RJ', 'Brazil', '20040-020', '+55 (21) 2271-7000', '+55 (21) 2271-7070', 'roberto.almeida@riotur.gov.br', 3),
        (13, 'Fernanda', 'Ramos', None, 'QNT 8 Lote 3', 'Brasília', 'DF', 'Brazil', '70174', '+55 (61) 3363-5547', '+55 (61) 3363-4467', 'fernr@terra.com.br', 4),
        (14, 'Mark', 'Philips', 'Telus', '8210 111 ST NW', 'Edmonton', 'AB', 'Canada', 'T6G 2C7', '+1 (780) 434-4554', '+1 (780) 434-5565', 'mphilips12@shaw.ca', 5),
        (15, 'Jennifer', 'Peterson', 'Rogers Canada', '700 W Pender Street', 'Vancouver', 'BC', 'Canada', 'V6C 1G8', '+1 (604) 688-2255', '+1 (604) 688-8756', 'jenniferp@rogers.ca', 3),
        (16, 'Frank', 'Harris', 'Google Inc.', '1600 Amphitheatre Parkway', 'Mountain View', 'CA', 'USA', '94043-1351', '+1 (650) 253-0000', '+1 (650) 253-0000', 'fharris@google.com', 3),
        (17, 'Jack', 'Smith', 'Microsoft Corporation', '1 Microsoft Way', 'Redmond', 'WA', 'USA', '98052-8300', '+1 (425) 882-8080', '+1 (425) 882-8081', 'jacksmith@microsoft.com', 4),
        (18, 'Michelle', 'Brooks', None, '627 Broadway', 'New York', 'NY', 'USA', '10012-2612', '+1 (212) 221-3546', '+1 (212) 221-4679', 'michelleb@aol.com', 3),
        (19, 'Tim', 'Goyer', 'Apple Inc.', '1 Infinite Loop', 'Cupertino', 'CA', 'USA', '95014', '+1 (408) 996-1010', '+1 (408) 996-1011', 'tgoyer@apple.com', 3),
        (20, 'Dan', 'Miller', None, '541 Del Medio Avenue', 'Mountain View', 'CA', 'USA', '94040-111', '+1 (650) 644-3358', None, 'danmtv@gmail.com', 4),
        (21, 'Kathy', 'Chase', None, '801 W 4th Street', 'Reno', 'NV', 'USA', '89503', '+1 (775) 223-7665', None, 'kachase@hotmail.com', 5),
        (22, 'Heather', 'Leacock', None, '120 S Orange Ave', 'Orlando', 'FL', 'USA', '32801', '+1 (407) 999-7788', None, 'hleacock@gmail.com', 4),
        (23, 'John', 'Gordon', None, '6920 E Broadway Blvd', 'Tucson', 'AZ', 'USA', '85710-3908', '+1 (520) 670-4466', None, 'johngordon22@yahoo.com', 5),
        (24, 'Frank', 'Ralston', None, '162 E Superior Street', 'Chicago', 'IL', 'USA', '60611', '+1 (312) 332-3232', None, 'fralston@gmail.com', 3),
        (25, 'Victor', 'Stevens', None, '319 N. Frances Street', 'Madison', 'WI', 'USA', '53703', '+1 (608) 257-0597', None, 'vstevens@yahoo.com', 5),
        (26, 'Richard', 'Cunningham', None, '2211 W Berry Street', 'Fort Worth', 'TX', 'USA', '76110', '+1 (817) 924-7272', None, 'ricunningham@hotmail.com', 4),
        (27, 'Patrick', 'Gray', None, '1033 N Park Ave', 'Tucson', 'AZ', 'USA', '85719', '+1 (520) 622-4200', None, 'patrick.gray@aol.com', 4),
        (28, 'Julia', 'Barnett', None, '302 S 700 E', 'Salt Lake City', 'UT', 'USA', '84102', '+1 (801) 531-7272', None, 'jubarnett@gmail.com', 5),
        (29, 'Robert', 'Brown', None, '796 Dundas Street West', 'Toronto', 'ON', 'Canada', 'M6J 1V1', '+1 (416) 363-8888', None, 'robbrown@shaw.ca', 3),
        (30, 'Edward', 'Francis', None, '230 Elgin Street', 'Ottawa', 'ON', 'Canada', 'K2P 1L7', '+1 (613) 234-3322', None, 'edfrancis@yaho.ca', 3),
        (31, 'Zack', 'Neverpurchased', 'Test Corp', '100 Void Street', 'Nowhere', 'CA', 'USA', '99999', '+1 (555) 000-0000', None, 'zack@neverpurchased.com', 3)
    ]
    cur.executemany('INSERT INTO customers (CustomerId, FirstName, LastName, Company, Address, City, State, Country, PostalCode, Phone, Fax, Email, SupportRepId) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', customers)

    playlists = [
        (1, 'Music'), (2, 'Movies'), (3, 'TV Shows'), (4, 'Audiobooks'),
        (5, '90s Music'), (6, 'Audiobooks'), (7, 'Movies'), (8, 'Music'),
        (9, 'Music Videos'), (10, 'TV Shows'), (11, 'Brazilian Music'),
        (12, 'Classical'), (13, 'Classical 101'), (14, 'Heavy Metal'),
        (15, 'Grunge'), (16, 'Rock Essentials'), (17, 'Jazz Masterpieces'),
        (18, 'On-The-Go 1')
    ]
    cur.executemany('INSERT INTO playlists (PlaylistId, Name) VALUES (?, ?)', playlists)

    track_data = []
    track_id = 1
    for album_id, title, artist_id in albums:
        for i in range(1, 5):
            name = f"{title} - Track {i}"
            genre_id = (album_id % 10) + 1
            media_type_id = 1 if track_id % 3 != 0 else 2
            composer = f"Composer {artist_id}"
            millis = 180000 + (track_id * 3500) % 240000
            bytes_val = millis * 128
            price = 0.99 if track_id % 5 != 0 else 1.99
            track_data.append((track_id, name, album_id, media_type_id, genre_id, composer, millis, bytes_val, price))
            track_id += 1

    cur.executemany('INSERT INTO tracks (TrackId, Name, AlbumId, MediaTypeId, GenreId, Composer, Milliseconds, Bytes, UnitPrice) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', track_data)

    pt_data = []
    for tid in range(1, len(track_data) + 1):
        pt_data.append((1, tid))
        if tid % 2 == 0:
            pt_data.append((5, tid))
        if tid % 3 == 0:
            pt_data.append((14, tid))
        if tid % 4 == 0:
            pt_data.append((16, tid))
    cur.executemany('INSERT INTO playlist_track (PlaylistId, TrackId) VALUES (?, ?)', pt_data)

    invoices_data = []
    items_data = []
    inv_id = 1
    line_id = 1

    # Top 5 spenders in 2024:
    # 1. Helena Holy (CustomerId 6) -> $48.50
    for total, date in [(15.84, '2024-01-15'), (12.87, '2024-03-20'), (9.90, '2024-06-10'), (9.89, '2024-09-05')]:
        invoices_data.append((inv_id, 6, date, 'Rilská 3174/6', 'Prague', None, 'Czech Republic', '14300', total))
        for k in range(int(round(total / 0.99))):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    # 2. Luis Goncalves (CustomerId 1) -> $39.60
    for total, date in [(19.80, '2024-02-14'), (19.80, '2024-07-22')]:
        invoices_data.append((inv_id, 1, date, 'Av. Brigadeiro Faria Lima, 2170', 'São José dos Campos', 'SP', 'Brazil', '12227-000', total))
        for k in range(int(round(total / 0.99))):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    # 3. Francois Tremblay (CustomerId 3) -> $34.65
    for total, date in [(13.86, '2024-04-11'), (20.79, '2024-08-19')]:
        invoices_data.append((inv_id, 3, date, '1498 rue Bélanger', 'Montréal', 'QC', 'Canada', 'H2G 1A7', total))
        for k in range(int(round(total / 0.99))):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    # 4. Leonie Kohler (CustomerId 2) -> $29.70
    for total, date in [(14.85, '2024-05-02'), (14.85, '2024-10-12')]:
        invoices_data.append((inv_id, 2, date, 'Theodor-Heuss-Straße 34', 'Stuttgart', None, 'Germany', '70174', total))
        for k in range(int(round(total / 0.99))):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    # 5. Bjorn Hansen (CustomerId 4) -> $25.74
    for total, date in [(12.87, '2024-01-28'), (12.87, '2024-11-04')]:
        invoices_data.append((inv_id, 4, date, 'Ullevålsveien 14', 'Oslo', None, 'Norway', '0171', total))
        for k in range(int(round(total / 0.99))):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    # Invoices for remaining customers
    for cid in range(5, 31):
        c = customers[cid - 1]
        d2023 = f'2023-{(cid % 12) + 1:02d}-15'
        invoices_data.append((inv_id, cid, d2023, c[4], c[5], c[6], c[7], c[8], 13.86))
        for k in range(14):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

        d2024 = f'2024-{(cid % 12) + 1:02d}-18'
        invoices_data.append((inv_id, cid, d2024, c[4], c[5], c[6], c[7], c[8], 5.94))
        for k in range(6):
            tid = (line_id % len(track_data)) + 1
            items_data.append((line_id, inv_id, tid, 0.99, 1))
            line_id += 1
        inv_id += 1

    cur.executemany('INSERT INTO invoices (InvoiceId, CustomerId, InvoiceDate, BillingAddress, BillingCity, BillingState, BillingCountry, BillingPostalCode, Total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', invoices_data)
    cur.executemany('INSERT INTO invoice_items (InvoiceLineId, InvoiceId, TrackId, UnitPrice, Quantity) VALUES (?, ?, ?, ?, ?)', items_data)

    conn.commit()
    conn.close()
    print(f"Database created at {db_path} with {len(customers)} customers, {len(invoices_data)} invoices, {len(track_data)} tracks, {len(artists)} artists.")

if __name__ == "__main__":
    create_and_populate("store.db")
