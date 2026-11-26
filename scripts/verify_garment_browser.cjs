// Called by verify_conversational_garment.py --browser using an isolated local account.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const crypto = require('node:crypto');

async function main(){
  const browser = await chromium.launch({channel:'chromium',args:['--enable-unsafe-swiftshader']});
  try {
    const stage = process.env.CHAT_RECOVERY_STAGE;
    const stateFile = process.env.CHAT_RECOVERY_STATE;
    const page = await browser.newPage({viewport:{width:1440,height:1000},
      storageState:stage === 'recover' ? stateFile : undefined});
    page.on('pageerror', error=>console.error('Browser error:',error.message));
    page.on('response', async res=>{
      if (/garment-turns$/.test(res.url()) && res.request().method()==='POST') {
        console.log('Garment turn HTTP',res.status());
      }
    });
    const origin = process.env.CHAT_TEST_ORIGIN;
    await page.route('**/*',route=>{
      const u = new URL(route.request().url());
      return u.origin === origin || ['blob:', 'data:'].includes(u.protocol) ? route.continue() : route.abort();
    });
    await page.addInitScript(session=>{
      localStorage.setItem('sb-127-auth-token',JSON.stringify(session));
      localStorage.setItem('yorvyn_profile_'+session.user.id,JSON.stringify({onboardingCompleted:true}));
    },JSON.parse(process.env.CHAT_TEST_SESSION));
    await page.goto(origin+'/stylist',{waitUntil:'domcontentloaded'});
    if (stage === 'recover') {
      const link = page.getByRole('link',{name:'Download GLB'}).nth(1);
      await link.waitFor({timeout:90000});
      const recovered = await hash(link);
      if (recovered !== process.env.CHAT_RECOVERY_HASH) throw Error('Recovered browser download differs');
      await page.locator('canvas[data-garment-loaded="true"]').nth(1).waitFor({timeout:60000});
      return;
    }
    const photos=page.locator('input[aria-label="Attach garment photos"]').first();
    await photos.setInputFiles(process.argv[2],{timeout:60000});
    const input=page.locator('.stylist-text-input:visible').first();
    async function send(text){
      await input.fill(text);
      await input.press('Enter');
    }
    await send(process.env.CHAT_INSTRUCTION || 'Create a 3D version of this denim jacket.');
    await page.getByRole('status').filter({hasText:/Locating garments|Analyzing the selected garment|Submitting reconstruction/}).first().waitFor({timeout:60000});
    const links=page.getByRole('link',{name:'Download GLB'});
    await links.first().waitFor({timeout:180000});
    const preview=page.locator('canvas[data-garment-loaded="true"]');
    await preview.first().waitFor();
    async function hash(link) {
      const event=page.waitForEvent('download');
      await link.click();
      return crypto.createHash('sha256').update(await fs.readFile(await (await event).path())).digest('hex');
    }
    const original=await hash(links.first());
    await send('Make it wider.');
    await links.nth(1).waitFor({timeout:60000});
    await page.getByText('Compare dimensions', {exact: true}).first().click();
    const width = await page.getByRole('row').filter({has:page.getByRole('rowheader',{name:'Width'})}).first().getByRole('cell').allTextContents();
    if (!(parseFloat(width[1]) > parseFloat(width[0]))) throw Error('Expected wider measured geometry');
    if(await hash(links.nth(1))===original) throw Error('Edited asset is unchanged');
    if (stage === 'create') {
      const user = JSON.parse(process.env.CHAT_TEST_SESSION).user.id;
      const session = await page.evaluate(id=>localStorage.getItem('yorvyn_garment_chat_'+id),user);
      if (!session) throw Error('Missing garment conversation');
      await fs.writeFile(process.env.CHAT_RECOVERY_SESSION,session,{mode:0o600});
      await page.context().storageState({path:stateFile});
      return;
    }
    await send('Undo');
    await links.nth(2).waitFor({timeout:60000});
    if(await hash(links.nth(2))!==original) throw Error('Undo did not restore the original');
    await page.reload({waitUntil:'domcontentloaded'});
    await links.nth(2).waitFor({timeout:60000});
    await page.getByRole('button',{name:'Try on',exact:true}).last().click();
    await page.getByRole('status').filter({hasText:/Fitted custom 3D/i}).first().waitFor({timeout:90000});
    console.log('Browser verified loaded preview, GLB downloads, edit, undo, history restoration and mesh attachment to the avatar.');
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1});
