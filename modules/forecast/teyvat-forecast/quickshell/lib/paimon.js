// paimon.js — deterministic Paimon-style lines for Teyvat Forecast.
// Pure JS (no QML access). PG-rated, cheerful, varied by condition.
// The line is picked with a day/hour-seeded index so it changes through
// the day but is identical for everyone seeing the same conditions.

.pragma library

var LINES = {
    rain: [
        "Umbrella time! Paimon does NOT want soggy shoes today.",
        "It's raining cats and wolves out there — stay dry, Traveler!",
        "Rainy days are perfect for a warm drink and a good story!",
        "Careful on the slippery stones! Paimon nearly floated away!"
    ],
    storm: [
        "Whoa! The sky is throwing a tantrum. Better stay inside!",
        "Thunder makes Paimon's hair stand up... let's wait this one out!",
        "Nope nope nope! Paimon is staying right here until the sky calms down!",
        "That lightning was HUGE! Paimon's heart is still racing!"
    ],
    snow: [
        "Brrr! Paimon can see her own breath! Bundle up warm!",
        "Snowball fight later? But first — mittens!",
        "The snow is so pretty... and SO cold. Scarf time, Traveler!",
        "Fresh snow means footprints! Let's go make some!"
    ],
    cold: [
        "It's freezing out there! A nice hot bowl of noodles would fix this.",
        "Cold hands, warm heart! But maybe bring gloves anyway.",
        "Brrr! Paimon recommends at least three layers of warm clothes!"
    ],
    fog: [
        "Careful, it's super foggy! Paimon can barely see her own hands!",
        "Stay close! In fog this thick we might walk right past a Hilichurl!",
        "The fog is so mysterious... like something out of a fairy tale!"
    ],
    windy: [
        "Hold onto your hat! The wind's in a mischievous mood today!",
        "Whoa! Anemo really wants to play today. Watch your cape!",
        "Winds like this are perfect for gliding! ...If you're brave!"
    ],
    muggy: [
        "Hot AND sticky?! It's like a sauna out there. Ew!",
        "Phew! The air feels like a wet blanket today. Light clothes!",
        "Paimon feels like a steamed bun! Let's find some shade!"
    ],
    hot: [
        "Phew! It's a barbecue out there — drink LOTS of water!",
        "Sunscreen time! Paimon refuses to let the sun eat you.",
        "So hot! An iced drink and a shady spot are mandatory!",
        "The sun means business today. Hat, water, shade. Paimon's orders!"
    ],
    air: [
        "The air's all yucky today... maybe skip the outdoor training?",
        "Ugh, the air feels heavy! A mask might be a good idea outside.",
        "The Abyss must be up to something — the air quality is awful!"
    ],
    night: [
        "The stars are SO pretty tonight! Make a wish, quick!",
        "What a calm night! Perfect for a little stargazing, hmm?",
        "The moon looks like a big juicy Custard Pie tonight..."
    ],
    overcast: [
        "Gray skies today... but Paimon's mood is still sunny!",
        "The clouds are having a meeting. A very long, very gray meeting.",
        "No sun? No problem! We carry our own light anyway!"
    ],
    nice: [
        "What a lovely day! Perfect for a picnic — or adventuring!",
        "The weather's great! Let's go exploring, Traveler!",
        "Paimon couldn't ask for better weather! Enjoy it!",
        "A perfect day to try that new restaurant, ehe~"
    ],
    stale: [
        "Huh? Paimon can't reach the weather network... is the internet napping?",
        "Paimon's crystal ball is all foggy... the data is old!",
        "The forecast is late! Someone go poke the weather network!"
    ]
};

function num(v, d) {
    return (v === undefined || v === null || isNaN(v)) ? d : v;
}

function pick(weather, date) {
    if (!weather) return "";
    var c = weather.current || {};
    var code = num(c.code, 0);
    var t = num(c.temperature, 15);
    var wind = num(c.wind_kmh, 0);
    var hum = num(c.humidity, 50);

    var rainy = (code >= 51 && code <= 67) || (code >= 80 && code <= 82);
    var stormy = code === 95 || code === 96 || code === 99;
    var snowy = (code >= 71 && code <= 77) || code === 85 || code === 86;
    var foggy = code === 45 || code === 48;
    var overcast = code === 3;

    var airBad = false;
    if (weather.air && weather.air.available && weather.air.eu_aqi !== null) {
        airBad = num(weather.air.eu_aqi, 0) > 80;
    }

    var cat;
    if (weather.stale) cat = "stale";
    else if (stormy) cat = "storm";
    else if (snowy) cat = "snow";
    else if (t <= 5) cat = "cold";
    else if (rainy) cat = "rain";
    else if (foggy) cat = "fog";
    else if (wind >= 35) cat = "windy";
    else if (t >= 28 && hum >= 70) cat = "muggy";
    else if (t >= 30) cat = "hot";
    else if (airBad) cat = "air";
    else if (num(c.is_day, 1) === 0) cat = "night";
    else if (overcast) cat = "overcast";
    else cat = "nice";

    var lines = LINES[cat] || LINES.nice;

    var day = Math.floor(date.getTime() / 86400000);
    var slot = Math.floor(date.getHours() / 6);
    var idx = (day * 7 + slot) % lines.length;
    return lines[idx];
}
