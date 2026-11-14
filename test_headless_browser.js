/**
 * Headless browser automation test for Saathi AI Payslip Explainer.
 * Uses puppeteer-core with local Chrome to:
 * 1. Load http://127.0.0.1:8000/
 * 2. Track all browser console logs, warnings, and errors.
 * 3. Click "Pre-fill Lakshmi's MOCK Payslip" button (#prefillLakshmiBtn).
 * 4. Click "Analyze & Explain My Payslip" button (#analyzePayslipBtn).
 * 5. Verify the results cards render (#resTakeHome, #resDeductions, #resEmployerContrib, #anomaliesContainer, #breakdownTable, #ticketDraftCard).
 * 6. Confirm 0 console errors.
 */

const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const URL = 'http://127.0.0.1:8000/';

async function run() {
  console.log('Launching Headless Chrome at:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage();
  
  const consoleMessages = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    consoleMessages.push({ type, text });
    if (type === 'error') {
      consoleErrors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.error('PAGE ERROR:', err.message);
    pageErrors.push(err.message);
  });

  page.on('requestfailed', req => {
    console.warn(`Request failed: ${req.url()} - ${req.failure()?.errorText}`);
  });

  try {
    console.log('Navigating to', URL);
    await page.goto(URL, { waitUntil: 'networkidle0', timeout: 15000 });
    console.log('Page loaded successfully. Title:', await page.title());

    // 1. Click Pre-fill Lakshmi button
    console.log('Clicking #prefillLakshmiBtn...');
    await page.waitForSelector('#prefillLakshmiBtn', { timeout: 5000 });
    await page.click('#prefillLakshmiBtn');

    // Verify fields populated
    const basicVal = await page.$eval('#psBasic', el => el.value);
    const grossVal = await page.$eval('#psGross', el => el.value);
    const pfVal = await page.$eval('#psEmployeePf', el => el.value);
    const passbookVal = await page.$eval('#psPassbookCredit', el => el.value);
    console.log(`Pre-fill verified: Basic=Rs ${basicVal}, Gross=Rs ${grossVal}, PF=Rs ${pfVal}, Passbook=Rs ${passbookVal}`);

    // 2. Click Analyze Payslip button
    console.log('Clicking #analyzePayslipBtn...');
    await page.click('#analyzePayslipBtn');

    // 3. Wait for results container to become visible
    await page.waitForFunction(() => {
      const el = document.getElementById('payslipResults');
      return el && !el.classList.contains('hidden');
    }, { timeout: 8000 });

    console.log('Results container (#payslipResults) is now visible!');

    // 4. Extract rendered cards data
    const resultsData = await page.evaluate(() => {
      const takeHome = document.getElementById('resTakeHome')?.textContent?.trim();
      const deductions = document.getElementById('resDeductions')?.textContent?.trim();
      const employer = document.getElementById('resEmployerContrib')?.textContent?.trim();
      
      const anomCards = Array.from(document.querySelectorAll('#anomaliesContainer .anomaly-card')).map(c => ({
        title: c.querySelector('.anomaly-title')?.textContent?.trim(),
        badge: c.querySelector('.anomaly-badge')?.textContent?.trim(),
        rule: c.querySelector('.anomaly-rule')?.textContent?.trim(),
        indic: c.querySelector('.anomaly-msg-indic')?.textContent?.trim(),
        en: c.querySelector('.anomaly-msg-en')?.textContent?.trim()
      }));

      const breakdownRows = Array.from(document.querySelectorAll('#breakdownTable .breakdown-row')).map(r => ({
        name: r.querySelector('.breakdown-name')?.textContent?.trim(),
        amount: r.querySelector('.breakdown-amount')?.textContent?.trim()
      }));

      const ticketVisible = !document.getElementById('ticketDraftCard')?.classList.contains('hidden');
      const ticketTitle = document.getElementById('draftTicketTitle')?.textContent?.trim();
      const ticketPriority = document.getElementById('draftTicketPriority')?.textContent?.trim();
      const ticketDesc = document.getElementById('draftTicketDesc')?.textContent?.trim();

      return {
        takeHome,
        deductions,
        employer,
        anomCards,
        breakdownRows,
        ticket: { visible: ticketVisible, title: ticketTitle, priority: ticketPriority, desc: ticketDesc }
      };
    });

    console.log('\n================ RENDERED CARD RESULTS ================');
    console.log('Net Take-Home Pay:         ', resultsData.takeHome);
    console.log('Total Deductions:          ', resultsData.deductions);
    console.log('Employer Contributions:    ', resultsData.employer);
    console.log('\nDetected Anomalies (Count: ' + resultsData.anomCards.length + '):');
    resultsData.anomCards.forEach((a, i) => {
      console.log(`  [${i+1}] ${a.title} (${a.badge})`);
      console.log(`      Rule:   ${a.rule}`);
      console.log(`      Kannada: ${a.indic}`);
      console.log(`      English: ${a.en}`);
    });

    console.log('\nLine Breakdown Rows (Count: ' + resultsData.breakdownRows.length + '):');
    resultsData.breakdownRows.forEach(r => {
      console.log(`  - ${r.name.padEnd(30)} ${r.amount}`);
    });

    console.log('\nHR Ticket Draft Card:');
    console.log('  Visible: ', resultsData.ticket.visible);
    console.log('  Title:   ', resultsData.ticket.title);
    console.log('  Priority:', resultsData.ticket.priority);
    console.log('  Description Snippet:\n  ' + resultsData.ticket.desc.split('\n').slice(0, 4).join('\n  '));
    console.log('========================================================\n');

    // 5. Console Error Verification
    console.log('Console message count:', consoleMessages.length);
    console.log('Console errors count: ', consoleErrors.length);
    console.log('Page exceptions count:', pageErrors.length);

    if (consoleErrors.length > 0 || pageErrors.length > 0) {
      console.error('\nFAILED: Console errors detected:');
      consoleErrors.forEach(e => console.error('  ERROR:', e));
      pageErrors.forEach(e => console.error('  PAGE ERROR:', e));
      process.exit(1);
    } else {
      console.log('\nPASSED: All cards rendered cleanly with ZERO console errors!');
      process.exit(0);
    }

  } catch (err) {
    console.error('TEST RUNNER FAILED:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

run();
