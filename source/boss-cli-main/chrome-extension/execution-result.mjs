export function singleExecutionResult(responses, stage) {
  if(!Array.isArray(responses) || responses.length!==1) throw new Error(stage+'：浏览器执行结果缺失或不唯一，结果待核实');
  const response=responses[0];
  if(response.error) throw new Error(stage+'：'+String(response.error.message||response.error));
  if(response.result==null) throw new Error(stage+'：浏览器未返回执行结果，结果待核实');
  return response.result;
}
