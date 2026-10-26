// Keep network/import failures visible instead of leaving a blank application.
import('./main').catch(error=>{
  console.error(error);
  const app=document.querySelector('#app');
  const heading=document.createElement('h1'); heading.textContent='Não foi possível carregar o grafo';
  const message=document.createElement('p'); message.textContent='Verifique se o servidor está em execução e recarregue a página.';
  const retry=document.createElement('button');retry.textContent='Tentar novamente';retry.onclick=()=>location.reload();
  app?.replaceChildren(heading,message,retry);
});
