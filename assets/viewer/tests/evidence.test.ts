import {test} from 'node:test';
import assert from 'node:assert/strict';
import {highlighted} from '../src/evidence-highlight';
const color=()=> '#21675c';
test('highlights reviewed plural aliases and avoids substrings',()=>{
 const result=highlighted('Computadores humanos executam; humanoide não.',[{entity:'human',text:'Computadores humanos',role:'entity'},{entity:'x',text:'humano',role:'entity'}],color);
 assert.equal(result.matched.has('human'),true);
 assert.equal(result.matched.has('x'),false);
});
test('escapes source markup without executing it',()=>{
 const result=highlighted('<img src=x onerror=alert(1)> Ada',[{entity:'ada',text:'Ada',role:'entity'}],color);
 assert.ok(result.html.includes('&lt;img'));
 assert.ok(!result.html.includes('<img'));
 assert.ok(result.html.includes('<mark'));
});
test('longest entity match wins over overlapping alias',()=>{
 const result=highlighted('Ada Lovelace',[{entity:'ada',text:'Ada Lovelace',role:'entity'},{entity:'short',text:'Ada',role:'entity'}],color);
 assert.deepEqual([...result.matched],['ada']);
});
test('literal relation is distinct from endpoint highlight',()=>{
 const result=highlighted('EDVAC consolida programa armazenado',[{entity:'edvac',text:'EDVAC',role:'entity'},{entity:'edvac',text:'consolida',role:'relation'}],color);
 assert.ok(result.html.includes('relation-highlight'));assert.ok(result.matched.has('relation'));
});
