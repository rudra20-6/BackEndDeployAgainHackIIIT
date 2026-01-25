const mongoose = require('mongoose');
require('dotenv').config();

mongoose.connect(process.env.MONGODB_URI);

const User = require('./models/User');

async function test() {
    const user = await User.findOne({ email: 'canteen1769281050094@example.com' });
    console.log('\n=== User from DB (default find) ===');
    console.log(JSON.stringify(user, null, 2));
    console.log('\ncanteenId field:', user.canteenId);
    console.log('canteenId type:', typeof user.canteenId);
    process.exit(0);
}

test().catch(err => {
    console.error(err);
    process.exit(1);
});
