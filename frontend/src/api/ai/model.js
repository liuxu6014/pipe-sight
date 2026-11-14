import request from "../pipeline/request";
import { requireBusinessId } from "@/utils/portal/businessId";

// 查询AI模型列表
export function listModel(query) {
  return request({
    url: "/ai/model/list",
    method: "get",
    params: query,
  });
}

// 查询所有AI模型列表
export function listModelAll() {
  return request({
    url: "/ai/model/all",
    method: "get",
  });
}

function generationPurpose(purpose) {
  if (!['image', 'digest', 'research'].includes(purpose)) throw new Error('生成模型用途不合法');
  return purpose;
}
export function getGenerationModelConfig(purpose) {
  return request({ url: `/ai/model/purpose-config/${generationPurpose(purpose)}`, method: 'get' });
}
export function updateGenerationModelConfig(purpose, data) {
  return request({ url: `/ai/model/purpose-config/${generationPurpose(purpose)}`, method: 'put', data });
}

export function getProcessingModelConfig() {
  return request({ url: '/ai/model/processing-config', method: 'get' });
}

export function updateProcessingModelConfig(data) {
  return request({ url: '/ai/model/processing-config', method: 'put', data });
}

export function getTranslationModelConfig() {
  return request({ url: '/ai/model/translation-config', method: 'get' });
}

export function updateTranslationModelConfig(data) {
  return request({ url: '/ai/model/translation-config', method: 'put', data });
}

// 查询AI模型详细
export function getModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId),
    method: "get",
  });
}

// 新增AI模型
export function addModel(data) {
  return request({
    url: "/ai/model",
    method: "post",
    data: data,
  });
}

// 修改AI模型
export function updateModel(data) {
  return request({
    url: "/ai/model",
    method: "put",
    data: data,
  });
}

// 删除AI模型
export function delModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId),
    method: "delete",
  });
}

// 测试AI模型连通性
export function testModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId) + "/test",
    method: "post",
  });
}
