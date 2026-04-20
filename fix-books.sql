-- Xóa duplicate books (giữ lại id 1-30)
-- Trước tiên update foreign keys trong các bảng liên quan nếu có
-- Xóa books id 31-120
DELETE FROM app_book WHERE id > 30;

-- Update cover_image_url đúng và unique cho từng cuốn (dùng Open Library ISBN covers)
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780743273565-L.jpg' WHERE id = 1;  -- The Great Gatsby
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780061935466-L.jpg' WHERE id = 2;  -- To Kill a Mockingbird
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg' WHERE id = 3;  -- 1984
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780141439518-L.jpg' WHERE id = 4;  -- Pride and Prejudice
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780316769174-L.jpg' WHERE id = 5;  -- The Catcher in the Rye
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780060850524-L.jpg' WHERE id = 6;  -- Brave New World
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780062315007-L.jpg' WHERE id = 7;  -- The Alchemist
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780439708180-L.jpg' WHERE id = 8;  -- Harry Potter
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780618640157-L.jpg' WHERE id = 9;  -- Lord of the Rings
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780451526342-L.jpg' WHERE id = 10; -- Animal Farm
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780553380163-L.jpg' WHERE id = 11; -- A Brief History of Time
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780192860927-L.jpg' WHERE id = 12; -- The Selfish Gene
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780345539434-L.jpg' WHERE id = 13; -- Cosmos
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780140432053-L.jpg' WHERE id = 14; -- The Origin of Species
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780393609394-L.jpg' WHERE id = 15; -- Astrophysics for People in a Hurry
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780132350884-L.jpg' WHERE id = 16; -- Clean Code
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780135957059-L.jpg' WHERE id = 17; -- The Pragmatic Programmer
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780201633610-L.jpg' WHERE id = 18; -- Design Patterns
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780262033848-L.jpg' WHERE id = 19; -- Introduction to Algorithms
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9781593279288-L.jpg' WHERE id = 20; -- Python Crash Course
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9781491924464-L.jpg' WHERE id = 21; -- You Don't Know JS
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780465026562-L.jpg' WHERE id = 22; -- Gödel, Escher, Bach
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9781857025217-L.jpg' WHERE id = 23; -- Fermat's Last Theorem
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780786884063-L.jpg' WHERE id = 24; -- The Man Who Loved Only Numbers
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780062316097-L.jpg' WHERE id = 25; -- Sapiens
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780393317558-L.jpg' WHERE id = 26; -- Guns, Germs, and Steel
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9781590302255-L.jpg' WHERE id = 27; -- The Art of War
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780062397348-L.jpg' WHERE id = 28; -- A People's History
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780553296983-L.jpg' WHERE id = 29; -- The Diary of a Young Girl
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/isbn/9780062464316-L.jpg' WHERE id = 30; -- Homo Deus

SELECT id, title, cover_image_url FROM app_book ORDER BY id;
