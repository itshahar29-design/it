// let go = ['eshmat', 'toshmat'];
// let email = 'KAMRON111@GMAIL.COM';

// console.log(email.indexOf('M'));        // 2 (birinchi 'M' pozitsiyasi)
// console.log(email.lastIndexOf('M'));     // 18 (oxirgi 'M' pozitsiyasi)
// console.log(email.slice(6, 9));          // "111"
// console.log(email.substr(2));            // "MRON111@GMAIL.COM"
// console.log(email.replace('N', 'M'));    // "KAMRON111@GMAIL.COM"
// console.log(email.charAt(0));            // "K"
// console.log(email.split(''));            // har bir harfdan iborat array
// console.log(go.join());                  // "eshmat,toshmat"

// let p = 6 > 9;
// let k = 99 > 98;
// let r = 8 >= 8;

// console.log(p); // false
// console.log(k); // true
// console.log(r); // true

let email = "ahrorboboqulov@gmail.com";     
console.log(email.indexOf('@'));
let text = "JavaScript juda qiziqarli";
console.log(text.indexOf('a'));
let phone = "+998901234567";
console.log(phone.indexOf('9'));
let word = "programmalash";
console.log(word.lastIndexOf('a'));
let userEmail = "webdeveloper@gmail.com";
console.log(userEmail.lastIndexOf('m'));
let greeting = "salom dunyo salom";
console.log(greeting.lastIndexOf('salom'));
let fullname = "Ali Valiyev";
console.log(fullname.slice(0, 3));
let userPhone = "+998901234567";
console.log(userPhone.slice(4, 6));
let contactEmail = "frontend@gmail.com";
console.log(contactEmail.slice(0, 8));
let language = "JavaScript";
console.log(language.substr(3, 4));
let city = "Tashkent";
console.log(city.substr(2, 5));
let password = "abcdef12345";
console.log(password.substr(0, 6));
let sentence = "Men CSS ni yaxshi ko'raman";
console.log(sentence.replace('CSS', 'JavaScript'));
let mobileNumber = "+998901234567";
console.log(mobileNumber.replace('998', '7'));
let dayInfo = "Bugun dushanba";
console.log(dayInfo.replace('dushanba', 'yakshanba'));
let name = "Aziz";
console.log(name.charAt(0));
let country = "Uzbekistan";
console.log(country.charAt(country.length - 1));
let adminEmail = "admin@gmail.com";
console.log(adminEmail.charAt(5));
let fruits = "Olma,Banan,Uzum";
console.log(fruits.split(','));
let clientName = "Ali Valiyev";
console.log(clientName.split(' '));
let date = "15-07-2026";
console.log(date.split('-'));
let fruitList = ["Olma", "Banan", "Shaftoli"];
console.log(fruitList.join(' - '));
let phoneParts = ["+998", "90", "123", "45", "67"];
console.log(phoneParts.join(''));
let words = ["JavaScript", "eng", "zo'r"];
console.log(words.join(' '))
let devEmail = "developer@gmail.com";
let atIndex = devEmail.indexOf('@');
console.log(atIndex);
let username = devEmail.slice(0, atIndex);
console.log(username);
console.log(devEmail.replace('developer', 'coder'));
let personName = "Ali Valiyev";
let ism = personName.slice(0, 3);
let familiya = personName.slice(4);
let nameArr = [ism, familiya];
console.log(nameArr);
console.log(nameArr.join(' - '));
let contactPhone = "+998901234567";
let operatorKod = contactPhone.slice(4, 6);
console.log(operatorKod);
let oxirgiRaqam = contactPhone.charAt(contactPhone.length - 1);
console.log(oxirgiRaqam);
console.log(contactPhone.replace('998', '7'));