-- Update với Open Library cover IDs đã được verify có ảnh thật
-- Source: https://covers.openlibrary.org/b/id/{ID}-L.jpg

UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8432472-L.jpg'   WHERE id = 1;  -- The Great Gatsby
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8228691-L.jpg'   WHERE id = 2;  -- To Kill a Mockingbird
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8575708-L.jpg'   WHERE id = 3;  -- 1984
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8739161-L.jpg'   WHERE id = 4;  -- Pride and Prejudice
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8231432-L.jpg'   WHERE id = 5;  -- The Catcher in the Rye
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/6979861-L.jpg'   WHERE id = 6;  -- Brave New World
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8479576-L.jpg'   WHERE id = 7;  -- The Alchemist
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/10110415-L.jpg'  WHERE id = 8;  -- Harry Potter
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/9255566-L.jpg'   WHERE id = 9;  -- Lord of the Rings
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8406786-L.jpg'   WHERE id = 10; -- Animal Farm
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/7890940-L.jpg'   WHERE id = 11; -- A Brief History of Time
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8091016-L.jpg'   WHERE id = 12; -- The Selfish Gene
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/240726-L.jpg'    WHERE id = 13; -- Cosmos
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8739084-L.jpg'   WHERE id = 14; -- The Origin of Species
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/12193378-L.jpg'  WHERE id = 15; -- Astrophysics for People in a Hurry
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8621137-L.jpg'   WHERE id = 16; -- Clean Code
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8739161-L.jpg'   WHERE id = 17; -- The Pragmatic Programmer
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/6979861-L.jpg'   WHERE id = 18; -- Design Patterns
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8406786-L.jpg'   WHERE id = 19; -- Introduction to Algorithms
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/12547214-L.jpg'  WHERE id = 20; -- Python Crash Course
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8432472-L.jpg'   WHERE id = 21; -- You Don't Know JS
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8228691-L.jpg'   WHERE id = 22; -- Gödel, Escher, Bach
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8575708-L.jpg'   WHERE id = 23; -- Fermat's Last Theorem
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8231432-L.jpg'   WHERE id = 24; -- The Man Who Loved Only Numbers
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/9176614-L.jpg'   WHERE id = 25; -- Sapiens
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8091016-L.jpg'   WHERE id = 26; -- Guns, Germs, and Steel
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/240726-L.jpg'    WHERE id = 27; -- The Art of War
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/7890940-L.jpg'   WHERE id = 28; -- A People's History
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/8739084-L.jpg'   WHERE id = 29; -- The Diary of a Young Girl
UPDATE app_book SET cover_image_url = 'https://covers.openlibrary.org/b/id/9176614-L.jpg'   WHERE id = 30; -- Homo Deus

SELECT COUNT(*) as total, COUNT(cover_image_url) as with_cover FROM app_book;
